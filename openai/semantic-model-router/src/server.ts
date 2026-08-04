import process from "node:process";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import {
  CONTROL_PLANE_PHASE,
  PLUGIN_NAME,
  PLUGIN_VERSION,
  routerDataDir,
} from "./config.js";
import { safeErrorMessage } from "./security/redaction.js";
import { runMaintenance } from "./maintenance.js";
import {
  activatePolicyCandidate,
  cleanupPolicyData,
  countPendingPolicyCandidates,
  createPolicyCandidate,
  getActivePolicyRecord,
  readPolicyCandidate,
  rollbackPolicy,
} from "./learning/policy-store.js";
import {
  consumePromptReference,
  countPendingPrompts,
} from "./storage/prompt-spool.js";
import {
  countPendingTasks,
  deletePendingTask,
  forgetAllRouteData,
  forgetRepositoryData,
  rejectPendingTask,
  submitRouteFeedback,
} from "./storage/pending-tasks.js";
import { resumeApprovedTask, runWorkflow } from "./workflow/coordinator.js";

const server = new McpServer({ name: PLUGIN_NAME, version: PLUGIN_VERSION });

server.registerTool(
  "run_route_maintenance",
  {
    title: "Run route maintenance",
    description:
      "Run weekly retention and candidate generation. Candidate activation remains a separate explicit action.",
    inputSchema: { force: z.boolean().optional() },
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  async ({ force }) => {
    try {
      const result = await runMaintenance(routerDataDir(), {
        ...(force !== undefined ? { force } : {}),
      });
      return {
        content: [{
          type: "text",
          text: [
            `maintenance: ${result.status}`,
            `run_id: ${result.runId}`,
            `removed_records: ${result.removedRecords}`,
            ...(result.candidateId ? [`candidate_id: ${result.candidateId}`, `candidate_state: ${result.candidateState}`] : []),
            ...(result.reason ? [`reason: ${result.reason}`] : []),
          ].join("\n"),
        }],
      };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "create_policy_candidate",
  {
    title: "Create policy candidate",
    description:
      "Build a data-only routing policy candidate from strong feedback and frozen replay cases. Does not change active policy.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: false,
    },
  },
  async () => {
    try {
      const candidate = await createPolicyCandidate(routerDataDir());
      return {
        content: [
          {
            type: "text",
            text: `Policy candidate: ${candidate.candidateId} | state: ${candidate.state} | accepted: ${candidate.evaluation.accepted} | accuracy: ${candidate.evaluation.candidate.weightedAccuracy.toFixed(3)} | S recall: ${candidate.evaluation.candidate.sRouteRecall.toFixed(3)} | Sol calls: ${candidate.evaluation.candidate.solCalls}`,
          },
        ],
      };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "review_policy_candidate",
  {
    title: "Review policy candidate",
    description: "Return sanitized replay metrics and release-gate reasons for one policy candidate.",
    inputSchema: { candidate_id: z.string().regex(/^policy-candidate-[A-Za-z0-9_-]{8,128}$/) },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  async ({ candidate_id }) => {
    try {
      const candidate = await readPolicyCandidate(routerDataDir(), candidate_id);
      const evaluation = candidate.evaluation;
      return {
        content: [
          {
            type: "text",
            text: [
              `candidate_id: ${candidate.candidateId}`,
              `state: ${candidate.state}`,
              `confidence_threshold: ${candidate.spec.confidenceThreshold}`,
              `baseline_accuracy: ${evaluation.baseline.weightedAccuracy.toFixed(3)}`,
              `candidate_accuracy: ${evaluation.candidate.weightedAccuracy.toFixed(3)}`,
              `candidate_s_recall: ${evaluation.candidate.sRouteRecall.toFixed(3)}`,
              `missed_high_risk: ${evaluation.candidate.missedHighRisk}`,
              `baseline_sol_calls: ${evaluation.baseline.solCalls}`,
              `candidate_sol_calls: ${evaluation.candidate.solCalls}`,
              `accepted: ${evaluation.accepted}`,
              `reasons: ${evaluation.reasons.join(",") || "none"}`,
            ].join("\n"),
          },
        ],
      };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "activate_policy_candidate",
  {
    title: "Activate policy candidate",
    description: "Activate an eligible data-only policy candidate after explicit confirmation.",
    inputSchema: {
      candidate_id: z.string().regex(/^policy-candidate-[A-Za-z0-9_-]{8,128}$/),
      confirmation: z.literal("ACTIVATE_POLICY"),
    },
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: false,
    },
  },
  async ({ candidate_id, confirmation }) => {
    try {
      const active = await activatePolicyCandidate(routerDataDir(), candidate_id, confirmation);
      return { content: [{ type: "text", text: `Policy activated: ${active.spec.versionId}` }] };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "rollback_policy",
  {
    title: "Rollback policy",
    description: "Restore the immediately previous data-only policy version after explicit confirmation.",
    inputSchema: {
      version_id: z.string().regex(/^[A-Za-z0-9_.-]{1,128}$/),
      confirmation: z.literal("ROLLBACK_POLICY"),
    },
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: false,
    },
  },
  async ({ version_id, confirmation }) => {
    try {
      const active = await rollbackPolicy(routerDataDir(), version_id, confirmation);
      return { content: [{ type: "text", text: `Policy rolled back to: ${active.spec.versionId}` }] };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "run_route_retention",
  {
    title: "Run route retention",
    description: "Remove expired weak-feedback and inactive policy candidate records; strong feedback remains.",
    inputSchema: { confirmation: z.literal("RUN_RETENTION") },
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  async ({ confirmation }) => {
    try {
      if (confirmation !== "RUN_RETENTION") throw new Error("Explicit retention confirmation required");
      const removed = await cleanupPolicyData(routerDataDir());
      return { content: [{ type: "text", text: `Route retention removed: ${removed}` }] };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "route_task",
  {
    title: "Route task",
    description:
      "Consume one opaque prompt reference, classify it, and run the bounded L or S workflow.",
    inputSchema: {
      prompt_ref: z
        .string()
        .regex(/^[a-f0-9]{16}\.[a-f0-9-]{36}$/, "Invalid prompt reference"),
    },
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: false,
    },
  },
  async ({ prompt_ref }) => {
    try {
      const envelope = await consumePromptReference(routerDataDir(), prompt_ref);
      const dataDir = routerDataDir();
      const workflow = await runWorkflow(envelope, undefined, undefined, { dataDir });
      const requested = envelope.override ?? "auto";
      const risks = envelope.riskTags.length
        ? envelope.riskTags.join(",")
        : "none";
      const context = risks === "none" ? requested : `${requested}; risk=${risks}`;
      return {
        content: [
          {
            type: "text",
            text: `${workflow.receipt} | requested: ${context}\n${workflow.summary}`,
          },
        ],
      };
    } catch (error) {
      return {
        isError: true,
        content: [{ type: "text", text: safeErrorMessage(error) }],
      };
    }
  },
);

server.registerTool(
  "approve_task",
  {
    title: "Approve task",
    description:
      "Consume one opaque approval token and resume the pending task. Approval is single-use.",
    inputSchema: {
      task_id: z.string().regex(/^task-[A-Za-z0-9_-]{8,128}$/),
      approval_token: z.string().regex(/^approval-[A-Za-z0-9_-]{8,128}$/),
    },
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: false,
    },
  },
  async ({ task_id, approval_token }) => {
    try {
      const workflow = await resumeApprovedTask(
        routerDataDir(),
        task_id,
        approval_token,
      );
      return {
        content: [{ type: "text", text: `${workflow.receipt}\n${workflow.summary}` }],
      };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "reject_task",
  {
    title: "Reject task",
    description: "Reject and retain a pending task as a non-executed audit record.",
    inputSchema: { task_id: z.string().regex(/^task-[A-Za-z0-9_-]{8,128}$/) },
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  async ({ task_id }) => {
    try {
      await rejectPendingTask(routerDataDir(), task_id);
      return { content: [{ type: "text", text: `Task rejected: ${task_id}` }] };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "submit_route_feedback",
  {
    title: "Submit route feedback",
    description:
      "Record weak route feedback by default. Natural-language or other feedback becomes strong only with explicit confirmation.",
    inputSchema: {
      task_id: z.string().regex(/^task-[A-Za-z0-9_-]{8,128}$/),
      label: z.enum(["correct", "incorrect"]),
      confirmation: z.boolean().optional(),
      comment: z.string().max(2000).optional(),
    },
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: false,
    },
  },
  async ({ task_id, label, confirmation, comment }) => {
    try {
      const feedback = await submitRouteFeedback(routerDataDir(), {
        taskId: task_id,
        label,
        ...(confirmation !== undefined ? { confirmation } : {}),
        ...(comment !== undefined ? { comment } : {}),
      });
      return {
        content: [{ type: "text", text: `Feedback recorded: ${feedback.strength}` }],
      };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "delete_task",
  {
    title: "Delete task record",
    description: "Delete one local pending-task record after explicit confirmation; no repository action is performed.",
    inputSchema: {
      task_id: z.string().regex(/^task-[A-Za-z0-9_-]{8,128}$/),
      confirmation: z.literal("DELETE_TASK"),
    },
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  async ({ task_id }) => {
    try {
      const removed = await deletePendingTask(routerDataDir(), task_id);
      return { content: [{ type: "text", text: removed ? `Task deleted: ${task_id}` : "Task already absent" }] };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "forget_repo_data",
  {
    title: "Forget repository route data",
    description: "Delete local pending route records for one repository overlay identified by its opaque repo id.",
    inputSchema: {
      repo_id: z.string().regex(/^[a-f0-9]{24}$/),
      confirmation: z.literal("FORGET_REPO_DATA"),
    },
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  async ({ repo_id }) => {
    try {
      const removed = await forgetRepositoryData(routerDataDir(), repo_id);
      return { content: [{ type: "text", text: `Repository route records deleted: ${removed}` }] };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "forget_all_route_data",
  {
    title: "Forget all route data",
    description: "Delete all local pending and feedback records after an explicit destructive confirmation.",
    inputSchema: { confirmation: z.literal("DELETE_ALL_ROUTE_DATA") },
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  async ({ confirmation }) => {
    try {
      const removed = await forgetAllRouteData(routerDataDir(), confirmation);
      return { content: [{ type: "text", text: `All route records deleted: ${removed}` }] };
    } catch (error) {
      return { isError: true, content: [{ type: "text", text: safeErrorMessage(error) }] };
    }
  },
);

server.registerTool(
  "get_router_status",
  {
    title: "Get router status",
    description:
      "Show local control-plane phase, dynamically resolved model roles, pending prompt count, and degraded state.",
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  async () => {
    try {
      const dataDir = routerDataDir();
      const pending = await countPendingPrompts(dataDir);
      const pendingTasks = await countPendingTasks(dataDir);
      const activePolicy = await getActivePolicyRecord(dataDir);
      const pendingCandidates = await countPendingPolicyCandidates(dataDir);
      const status = [
        `phase: ${CONTROL_PLANE_PHASE}`,
        "automatic_model_calls: bounded-lifecycle",
        "model_selection: auto from model/list with role-fit scoring",
        "classifier_target: role=classifier requested-effort=low",
        "planner_reviewer_target: role=planner/reviewer requested-effort=xhigh minimum=high",
        "executor_target: role=executor requested-effort=max",
        "manual_overrides: @luna/@sol force model family; @current bypasses routing",
        `pending_prompt_refs: ${pending}`,
        `pending_approval_tasks: ${pendingTasks}`,
        `active_policy: ${activePolicy.spec.versionId}`,
        `active_confidence_threshold: ${activePolicy.spec.confidenceThreshold}`,
        `pending_policy_candidates: ${pendingCandidates}`,
        "degraded: false",
      ].join("\n");
      return { content: [{ type: "text", text: status }] };
    } catch (error) {
      return {
        isError: true,
        content: [
          {
            type: "text",
            text: `phase: ${CONTROL_PLANE_PHASE}\ndegraded: true\nreason: ${safeErrorMessage(error)}`,
          },
        ],
      };
    }
  },
);

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(() => {
  process.exitCode = 1;
});
