import type { PromptEnvelope } from "../storage/prompt-spool.js";
import process from "node:process";
import {
  AppServerSupervisor,
  type AppServerTurnResult,
  type ReasoningEffort,
  type RoleTarget,
  type SandboxMode,
} from "../app-server/supervisor.js";
import { redactText } from "../security/redaction.js";
import {
  BASELINE_POLICY,
  getActivePolicy,
  type PolicySpec,
} from "../learning/policy-store.js";
import {
  approvePendingTask,
  completePendingTask,
  createPendingTask,
} from "../storage/pending-tasks.js";
import {
  classifierPrompt,
  parseClassifierResult,
  type Route,
} from "../routing/classifier.js";
import { decideRoute } from "../routing/policy.js";
import { detectRiskTags, type RiskTag } from "../routing/hard-rules.js";
import {
  parseTaskPacket,
  plannerPrompt,
  serializeTaskPacket,
  type TaskPacket,
} from "./task-packet.js";
import {
  parseReviewResult,
  reviewerPrompt,
  type ReviewResult,
} from "./reviewer.js";

export interface TurnRunner {
  runTurn(prompt: string, target: RoleTarget, signal?: AbortSignal): Promise<AppServerTurnResult>;
}

export interface WorkflowResult {
  route: Route | "current";
  status: "succeeded" | "awaiting_approval" | "blocked" | "degraded-current";
  receipt: string;
  summary: string;
  taskId?: string;
  approvalToken?: string;
}

export interface WorkflowOptions {
  dataDir?: string;
  approved?: boolean;
  policy?: PolicySpec;
}

const CLASSIFIER_TARGET: RoleTarget = {
  model: "auto",
  effort: "low",
  role: "classifier",
  sandbox: "read-only",
  approvalPolicy: "never",
};
const PLANNER_TARGET: RoleTarget = {
  model: "auto",
  effort: "xhigh",
  role: "planner",
  sandbox: "read-only",
  approvalPolicy: "never",
};

export async function runWorkflow(
  envelope: PromptEnvelope,
  runner: TurnRunner = createDefaultRunner(envelope),
  signal?: AbortSignal,
  options: WorkflowOptions = {},
): Promise<WorkflowResult> {
  const hardRiskTags = envelope.riskTags.length
    ? envelope.riskTags
    : detectRiskTags(envelope.prompt);
  if (hardRiskTags.length && options.approved !== true) {
    return awaitingApproval(envelope, hardRiskTags, options.dataDir);
  }

  let classifier;
  let classifierTurn: AppServerTurnResult | undefined;
  if (envelope.override) {
    classifier = undefined;
  } else {
    try {
      classifierTurn = await runner.runTurn(
        classifierPrompt(envelope.prompt),
        targetForRole(envelope, CLASSIFIER_TARGET),
        signal,
      );
      classifier = parseClassifierResult(classifierTurn.text);
    } catch {
      return degradedCurrent(envelope, "classifier unavailable");
    }
  }

  const policy = options.policy ?? (options.dataDir ? await getActivePolicy(options.dataDir) : BASELINE_POLICY);
  const decision = decideRoute({
    ...(envelope.override ? { override: envelope.override } : {}),
    hardRiskTags,
    ...(classifier ? { classifier } : {}),
    ...(options.approved !== undefined ? { approved: options.approved } : {}),
    confidenceThreshold: policy.confidenceThreshold,
    ambiguousToS: policy.ambiguousToS,
  });
  if (decision.requiresApproval && options.approved !== true) {
    return awaitingApproval(envelope, decision.riskTags, options.dataDir);
  }
  return decision.route === "L"
    ? runLRoute(envelope, decision.reasonCodes, decision.summary, runner, signal, classifierTurn)
    : runSRoute(envelope, decision.reasonCodes, decision.summary, runner, signal, classifierTurn);
}

export async function resumeApprovedTask(
  dataDir: string,
  taskId: string,
  approvalToken: string,
  runner?: TurnRunner,
  signal?: AbortSignal,
): Promise<WorkflowResult> {
  const approved = await approvePendingTask(dataDir, taskId, approvalToken);
  const envelope: PromptEnvelope = {
    version: 1,
    createdAt: approved.createdAt,
    expiresAt: approved.expiresAt,
    sessionKey: approved.sessionKey,
    turnKey: approved.turnKey,
    prompt: approved.taskPrompt,
    ...(approved.permissionMode !== undefined
      ? { permissionMode: approved.permissionMode }
      : {}),
    ...(approved.override !== undefined ? { override: approved.override } : {}),
    riskTags: approved.riskTags,
  };
  const workflow = await runWorkflow(
    envelope,
    runner ?? createDefaultRunner(envelope),
    signal,
    { approved: true, dataDir },
  );
  await completePendingTask(dataDir, taskId);
  return { ...workflow, taskId };
}

async function runLRoute(
  envelope: PromptEnvelope,
  reasonCodes: string[],
  reason: string,
  runner: TurnRunner,
  signal?: AbortSignal,
  classifierTurn?: AppServerTurnResult,
): Promise<WorkflowResult> {
  const target = executorTarget(envelope);
  try {
    const result = await runner.runTurn(executorPrompt(envelope.prompt), target, signal);
    return {
      route: "L",
      status: "succeeded",
      receipt: `Route: L | ${formatCalls([
        ...(classifierTurn ? [{ role: "classifier" as const, result: classifierTurn }] : []),
        { role: "executor", result },
      ])} | reason: ${formatReason(reasonCodes, reason, envelope.prompt)}`,
      summary: summarize(result.text, envelope.prompt),
    };
  } catch {
    return degradedCurrent(envelope, "executor unavailable");
  }
}

async function runSRoute(
  envelope: PromptEnvelope,
  reasonCodes: string[],
  reason: string,
  runner: TurnRunner,
  signal?: AbortSignal,
  classifierTurn?: AppServerTurnResult,
): Promise<WorkflowResult> {
  let solCalls = 0;
  let lunaCalls = 0;
  let packet: TaskPacket;
  let plannerTurn: AppServerTurnResult;
  try {
    const planned = await plan(envelope, runner, signal);
    packet = planned.packet;
    plannerTurn = planned.result;
    solCalls += 1;
  } catch {
    return blocked(sReceipt(reasonCodes, reason, envelope.prompt, classifierTurn), "planner unavailable");
  }

  let executionReport = "";
  let lastReview: ReviewResult | undefined;
  let executionTurn: AppServerTurnResult | undefined;
  let reviewTurn: AppServerTurnResult | undefined;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (lunaCalls >= 3) {
      return blocked(
        sReceipt(reasonCodes, reason, envelope.prompt, classifierTurn, plannerTurn, executionTurn, reviewTurn),
        "executor repair limit reached",
      );
    }
    try {
      const execution = await runner.runTurn(
        executorPrompt(envelope.prompt, packet, lastReview),
        executorTarget(envelope),
        signal,
      );
      executionTurn = execution;
      lunaCalls += 1;
      executionReport = summarize(execution.text, envelope.prompt);
    } catch {
      return blocked(
        sReceipt(reasonCodes, reason, envelope.prompt, classifierTurn, plannerTurn, executionTurn, reviewTurn),
        "executor unavailable",
      );
    }

    if (solCalls >= 4) {
      return blocked(
        sReceipt(reasonCodes, reason, envelope.prompt, classifierTurn, plannerTurn, executionTurn, reviewTurn),
        "reviewer limit reached",
      );
    }
    try {
      const review = await runner.runTurn(
        reviewerPrompt(envelope.prompt, serializeTaskPacket(packet), executionReport),
        targetForRole(envelope, { ...PLANNER_TARGET, role: "reviewer" }),
        signal,
      );
      reviewTurn = review;
      solCalls += 1;
      lastReview = parseReviewResult(review.text);
    } catch {
      return blocked(
        sReceipt(reasonCodes, reason, envelope.prompt, classifierTurn, plannerTurn, executionTurn, reviewTurn),
        "reviewer unavailable",
      );
    }
    if (!lastReview) {
      return blocked(
        sReceipt(reasonCodes, reason, envelope.prompt, classifierTurn, plannerTurn, executionTurn, reviewTurn),
        "reviewer returned invalid result",
      );
    }
    if (lastReview.status === "pass") {
      return {
        route: "S",
        status: "succeeded",
        receipt: `Route: S | ${formatCalls([
          ...(classifierTurn ? [{ role: "classifier" as const, result: classifierTurn }] : []),
          { role: "planner", result: plannerTurn },
          { role: "executor", result: executionTurn! },
          { role: "reviewer", result: reviewTurn! },
        ])} | reason: ${formatReason(reasonCodes, reason, envelope.prompt)}`,
        summary: summarize(lastReview.summary, envelope.prompt),
      };
    }
    if (lastReview.status === "block") {
      return blocked(
        sReceipt(reasonCodes, reason, envelope.prompt, classifierTurn, plannerTurn, executionTurn, reviewTurn),
        lastReview.summary,
      );
    }
    if (lastReview.majorDeviation) {
      if (solCalls >= 4) {
        return blocked(
          sReceipt(reasonCodes, reason, envelope.prompt, classifierTurn, plannerTurn, executionTurn, reviewTurn),
          "major deviation exceeded reviewer call limit",
        );
      }
      try {
        const replanned = await plan(
          envelope,
          runner,
          signal,
          `${envelope.prompt}\nReviewer found major deviation: ${lastReview.issues.join("; ")}`,
        );
        packet = replanned.packet;
        plannerTurn = replanned.result;
        solCalls += 1;
      } catch {
        return blocked(
          sReceipt(reasonCodes, reason, envelope.prompt, classifierTurn, plannerTurn, executionTurn, reviewTurn),
          "replanning unavailable",
        );
      }
    }
  }
  return blocked(
    sReceipt(reasonCodes, reason, envelope.prompt, classifierTurn, plannerTurn, executionTurn, reviewTurn),
    "repair limit reached",
  );
}

async function plan(
  envelope: PromptEnvelope,
  runner: TurnRunner,
  signal?: AbortSignal,
  prompt = envelope.prompt,
): Promise<{ packet: TaskPacket; result: AppServerTurnResult }> {
  const result = await runner.runTurn(
    plannerPrompt(prompt),
    targetForRole(envelope, PLANNER_TARGET),
    signal,
  );
  const packet = parseTaskPacket(result.text);
  if (!packet) throw new Error("Planner returned invalid task packet");
  return { packet, result };
}

function executorPrompt(prompt: string, packet?: TaskPacket, review?: ReviewResult): string {
  const parts = [
    "You are semantic-model-router execution role.",
    "Re-read current repository state before editing. Follow existing permissions and scope.",
    "Do not perform delete, overwrite, publish, deployment, credential, schema, permission, or external side effects unless explicitly approved.",
    "Return a concise sanitized implementation and verification summary; no chain-of-thought or full diff.",
    `User task:\n${prompt}`,
  ];
  if (packet) parts.push(`Task packet:\n${serializeTaskPacket(packet)}`);
  if (review) parts.push(`Reviewer issues to repair:\n${review.issues.join("; ")}`);
  return parts.join("\n");
}

function executorTarget(envelope: PromptEnvelope): RoleTarget {
  const permissions = permissionForMode(envelope.permissionMode);
  return {
    model: forcedModelFamily(envelope),
    effort: "max",
    role: "executor",
    ...(envelope.model ? { currentModel: envelope.model } : {}),
    sandbox: permissions.sandbox,
    approvalPolicy: permissions.approvalPolicy,
  };
}

function targetForRole(envelope: PromptEnvelope, target: RoleTarget): RoleTarget {
  return {
    ...target,
    model: forcedModelFamily(envelope, target.model),
    ...(envelope.model ? { currentModel: envelope.model } : {}),
  };
}

function forcedModelFamily(envelope: PromptEnvelope, fallback = "auto"): string {
  if (envelope.override === "L") return "luna";
  if (envelope.override === "S") return "sol";
  return fallback;
}

function permissionForMode(mode?: string): {
  sandbox: SandboxMode;
  approvalPolicy: "never" | "on-request";
} {
  switch (mode) {
    case "workspace-write":
      return { sandbox: "workspace-write", approvalPolicy: "on-request" };
    case "danger-full-access":
      return { sandbox: "danger-full-access", approvalPolicy: "on-request" };
    case "read-only":
      return { sandbox: "read-only", approvalPolicy: "never" };
    default:
      return { sandbox: "read-only", approvalPolicy: "never" };
  }
}

async function awaitingApproval(
  envelope: PromptEnvelope,
  riskTags: RiskTag[],
  dataDir?: string,
): Promise<WorkflowResult> {
  if (!dataDir) {
    return {
      route: "S",
      status: "awaiting_approval",
      receipt: `Route: S | awaiting approval | risk: ${riskTags.join(",")}`,
      summary: "high-risk task paused before executor creation",
    };
  }
  let pending;
  try {
    pending = await createPendingTask(dataDir, envelope, riskTags);
  } catch {
    return blocked(
      "Route: S | approval state unavailable | execution blocked",
      "cannot persist approval request",
    );
  }
  return {
    route: "S",
    status: "awaiting_approval",
    receipt: `Route: S | awaiting approval | task_id=${pending.taskId} | approval_token=${pending.approvalToken} | risk: ${riskTags.join(",")}`,
    summary: "high-risk task paused before executor creation; approve_task resumes it",
    taskId: pending.taskId,
    approvalToken: pending.approvalToken,
  };
}

function blocked(receipt: string, summary: string): WorkflowResult {
  return { route: "S", status: "blocked", receipt, summary: summarize(summary) };
}

function sReceipt(
  reasonCodes: string[],
  reason: string,
  prompt?: string,
  classifierTurn?: AppServerTurnResult,
  plannerTurn?: AppServerTurnResult,
  executionTurn?: AppServerTurnResult,
  reviewTurn?: AppServerTurnResult,
): string {
  const calls = [
    ...(classifierTurn ? [{ role: "classifier" as const, result: classifierTurn }] : []),
    ...(plannerTurn ? [{ role: "planner" as const, result: plannerTurn }] : []),
    ...(executionTurn ? [{ role: "executor" as const, result: executionTurn }] : []),
    ...(reviewTurn ? [{ role: "reviewer" as const, result: reviewTurn }] : []),
  ];
  return `Route: S | ${calls.length ? formatCalls(calls) : "auto S workflow"} | reason: ${formatReason(reasonCodes, reason, prompt)}`;
}

function formatCalls(
  calls: Array<{
    role: "classifier" | "planner" | "executor" | "reviewer";
    result: AppServerTurnResult;
  }>,
): string {
  return calls
    .map(({ role, result }) => `${role}=${result.model}/${result.effort}`)
    .join(" -> ");
}

function degradedCurrent(envelope: PromptEnvelope, reason: string): WorkflowResult {
  const current = envelope.model?.trim()
    ? redactText(envelope.model).replace(/[\r\n]+/g, " ").slice(0, 160)
    : "current model";
  return {
    route: "current",
    status: "degraded-current",
    receipt: `Route: degraded-current | ${reason} | current=${current}`,
    summary: `${reason}; current model retained`,
  };
}

function formatReason(reasonCodes: string[], summary: string, prompt?: string): string {
  let result = redactText([...reasonCodes, summary].join(" + "));
  if (prompt?.trim()) result = result.split(prompt).join("[TASK_REDACTED]");
  return result.replace(/[\r\n]+/g, " ").slice(0, 300);
}

function summarize(value: string, prompt?: string): string {
  let result = redactText(value || "completed");
  if (prompt?.trim()) result = result.split(prompt).join("[TASK_REDACTED]");
  return result.replace(/[\r\n]+/g, " ").slice(0, 2000);
}

function safeCwd(cwd?: string): string | undefined {
  return cwd && cwd.startsWith("/") ? cwd : undefined;
}

function createDefaultRunner(envelope: PromptEnvelope): TurnRunner {
  const cwd = safeCwd(envelope.cwd);
  const command = process.env.SEMANTIC_ROUTER_APP_SERVER_COMMAND;
  const args = parseAppServerArgs(process.env.SEMANTIC_ROUTER_APP_SERVER_ARGS);
  const options = {
    ...(cwd ? { cwd } : {}),
    ...(command?.trim() ? { command: command.trim() } : {}),
    ...(args ? { args } : {}),
  };
  return new AppServerSupervisor(options);
}

function parseAppServerArgs(value: string | undefined): string[] | undefined {
  if (!value) return undefined;
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed) && parsed.length <= 8 && parsed.every((item) => typeof item === "string")
      ? parsed
      : undefined;
  } catch {
    return undefined;
  }
}
