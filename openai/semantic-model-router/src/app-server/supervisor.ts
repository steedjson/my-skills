import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import process from "node:process";

import { redactText } from "../security/redaction.js";
import { AppServerClient, AppServerClientError } from "./client.js";
import {
  isRecord,
  type ModelListEntry,
  type ModelListResult,
  type ThreadSettingsUpdatedParams,
  type Turn,
  type TurnCompletedParams,
  type TurnStartResult,
} from "./protocol.js";

export type ReasoningEffort = "low" | "medium" | "high" | "xhigh" | "max" | "ultra";
export type SandboxMode = "read-only" | "workspace-write" | "danger-full-access";
export type ModelRole = "classifier" | "planner" | "executor" | "reviewer";
export type ModelFamily = "luna" | "sol";

export interface RoleTarget {
  model: string;
  effort: ReasoningEffort;
  sandbox: SandboxMode;
  role?: ModelRole;
  currentModel?: string;
  approvalPolicy?: "untrusted" | "on-request" | "never";
  selectionReason?: string;
}

export interface AppServerTurnResult {
  model: string;
  effort: ReasoningEffort;
  threadId: string;
  turnId: string;
  status: string;
  text: string;
  selectionReason?: string;
}

const EFFORT_ORDER: readonly ReasoningEffort[] = [
  "low",
  "medium",
  "high",
  "xhigh",
  "max",
  "ultra",
];

export interface AppServerSupervisorOptions {
  command?: string;
  args?: string[];
  cwd?: string;
  env?: NodeJS.ProcessEnv;
  timeoutMs?: number;
  requestTimeoutMs?: number;
  killGraceMs?: number;
  spawnProcess?: typeof spawn;
}

export class ModelPreflightError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ModelPreflightError";
  }
}

export class AppServerTurnError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AppServerTurnError";
  }
}

export class AppServerSupervisor {
  private readonly options: {
    command: string;
    args: string[];
    timeoutMs: number;
    requestTimeoutMs: number;
    killGraceMs: number;
    cwd?: string | undefined;
    env?: NodeJS.ProcessEnv | undefined;
    spawnProcess?: typeof spawn | undefined;
  };

  constructor(options: AppServerSupervisorOptions = {}) {
    this.options = {
      command: options.command ?? "codex",
      args: options.args ?? ["app-server"],
      timeoutMs: options.timeoutMs ?? 120_000,
      requestTimeoutMs: options.requestTimeoutMs ?? 30_000,
      killGraceMs: options.killGraceMs ?? 1_000,
      cwd: options.cwd,
      env: options.env,
      spawnProcess: options.spawnProcess,
    };
  }

  async runTurn(
    prompt: string,
    target: RoleTarget,
    signal?: AbortSignal,
  ): Promise<AppServerTurnResult> {
    if (!prompt.trim()) throw new AppServerTurnError("Prompt is empty");
    const child = this.startChild();
    const client = new AppServerClient(child, {
      requestTimeoutMs: this.options.requestTimeoutMs,
    });
    const timeout = AbortSignal.timeout(this.options.timeoutMs);
    const combined = combineSignals(signal, timeout);
    try {
      await client.initialize(combined);
      const models = await this.listModels(client, combined);
      const resolvedTargets = resolveRoleTargets(models, target);
      let lastError: unknown;
      for (const [index, resolvedTarget] of resolvedTargets.entries()) {
        try {
          return await this.runResolvedTurn(client, prompt, target, resolvedTarget, combined);
        } catch (error) {
          lastError = error;
          const canFallback =
            target.model === "auto" &&
            index < resolvedTargets.length - 1 &&
            isUnsupportedModelError(error);
          if (!canFallback) throw error;
          client.drainNotifications();
        }
      }
      throw lastError ?? new ModelPreflightError(`Requested model is unavailable: ${target.model}`);
    } catch (error) {
      if (error instanceof AppServerClientError || error instanceof ModelPreflightError || error instanceof AppServerTurnError) {
        throw error;
      }
      throw new AppServerTurnError(redactText(error instanceof Error ? error.message : String(error)));
    } finally {
      client.close();
      await terminateChild(child, this.options.killGraceMs);
    }
  }

  private startChild(): ChildProcessWithoutNullStreams {
    const spawnProcess = this.options.spawnProcess ?? spawn;
    const child = spawnProcess(this.options.command, this.options.args, {
      cwd: this.options.cwd,
      env: {
        ...process.env,
        ...this.options.env,
        SEMANTIC_ROUTER_CHILD: "1",
      },
      stdio: ["pipe", "pipe", "pipe"],
    });
    child.stderr.resume();
    return child as ChildProcessWithoutNullStreams;
  }

  private async listModels(client: AppServerClient, signal: AbortSignal): Promise<ModelListEntry[]> {
    const models: ModelListEntry[] = [];
    let cursor: string | null | undefined;
    do {
      const params: Record<string, unknown> = { includeHidden: true };
      if (cursor) params.cursor = cursor;
      const result = await client.request<ModelListResult>("model/list", params, signal);
      models.push(...(result.data ?? []));
      cursor = result.nextCursor;
    } while (cursor);
    return models;
  }

  private async runResolvedTurn(
    client: AppServerClient,
    prompt: string,
    target: RoleTarget,
    resolvedTarget: RoleTarget,
    signal: AbortSignal,
  ): Promise<AppServerTurnResult> {
    const threadStart = await client.request<Record<string, unknown>>("thread/start", {
      model: resolvedTarget.model,
      allowProviderModelFallback: false,
      ephemeral: true,
      cwd: this.options.cwd ?? process.cwd(),
      sandbox: target.sandbox,
      approvalPolicy: target.approvalPolicy ?? "never",
    }, signal);
    const threadId = readThreadId(threadStart);
    if (!threadId) throw new AppServerTurnError("App Server did not return a thread id");
    if (typeof threadStart.model === "string" && threadStart.model !== resolvedTarget.model) {
      throw new ModelPreflightError("App Server selected unexpected model");
    }
    const settingsResult = await client.request<Record<string, unknown>>("thread/settings/update", {
      threadId,
      model: resolvedTarget.model,
      effort: resolvedTarget.effort,
    }, signal);
    const settings = readThreadSettingsUpdated(settingsResult)?.threadSettings;
    if (settings && (settings.model !== resolvedTarget.model || settings.effort !== resolvedTarget.effort)) {
      throw new ModelPreflightError("App Server did not apply exact model settings");
    }
    const turnStart = await client.request<TurnStartResult>("turn/start", {
      threadId,
      input: [{ type: "text", text: prompt }],
    }, signal);
    const turnId = turnStart.turn?.id;
    if (!turnId) throw new AppServerTurnError("App Server did not return a turn id");
    const completedMessage = await client.waitForNotification(
      (message) =>
        message.method === "turn/completed" &&
        matchesTurn(message.params, threadId, turnId),
      this.options.requestTimeoutMs,
      signal,
    );
    const completed = readTurnCompleted(completedMessage.params);
    const turn = completed?.turn;
    if (!turn || turn.status !== "completed") {
      throw new AppServerTurnError(redactText(turn?.error?.message ?? "App Server turn failed"));
    }
    return {
      model: resolvedTarget.model,
      effort: resolvedTarget.effort,
      threadId,
      turnId,
      status: turn.status,
      text: extractTurnText(turn, client.drainNotifications()),
      ...(resolvedTarget.selectionReason
        ? { selectionReason: resolvedTarget.selectionReason }
        : {}),
    };
  }

}

export function resolveRoleTarget(models: ModelListEntry[], target: RoleTarget): RoleTarget {
  const selection = selectModel(models, target);
  if (!selection) throw new ModelPreflightError(`Requested model family is unavailable: ${target.model}`);
  return roleTargetFromCandidate(target, selection);
}

function resolveRoleTargets(models: ModelListEntry[], target: RoleTarget): RoleTarget[] {
  return selectModels(models, target).map((selection) => roleTargetFromCandidate(target, selection));
}

function roleTargetFromCandidate(target: RoleTarget, selection: ModelCandidate): RoleTarget {
  const role = target.role ?? inferRole(target.effort);
  const effortSelection =
    selection.effort === target.effort
      ? `effort=${selection.effort}`
      : `requested-effort=${target.effort} -> resolved-effort=${selection.effort}`;
  const selectionReason = [
    target.model === "auto" ? "auto" : `requested=${target.model}`,
    `role=${role}`,
    `model=${selection.id}`,
    effortSelection,
  ].join(" | ");
  return {
    ...target,
    model: selection.id,
    effort: selection.effort,
    selectionReason,
  };
}

interface ModelCandidate {
  entry: ModelListEntry;
  id: string;
  effort: ReasoningEffort;
  score: number;
}

function selectModel(
  models: ModelListEntry[],
  target: RoleTarget,
): ModelCandidate | undefined {
  return selectModels(models, target)[0];
}

function selectModels(
  models: ModelListEntry[],
  target: RoleTarget,
): ModelCandidate[] {
  const normalized = target.model.toLowerCase();
  const exact = models.find((entry) =>
    [entry.id, entry.model].some((value) => value?.toLowerCase() === normalized),
  );
  const family = modelFamily(target.model);
  if (target.model !== "auto" && !exact && !family) return [];
  const candidates = models
    .map((entry): ModelCandidate | undefined => {
      const id = entry.id ?? entry.model;
      if (!id) return undefined;
      const entryName = [entry.id, entry.model].filter(Boolean).join(" ").toLowerCase();
      if (exact && entry !== exact) return undefined;
      if (family && !entryName.includes(family)) return undefined;
      const supported = (entry.supportedReasoningEfforts ?? [])
        .map((item) => item.reasoningEffort)
        .filter((effort): effort is ReasoningEffort => EFFORT_ORDER.includes(effort as ReasoningEffort));
      let effort: ReasoningEffort;
      try {
        effort = resolveEffort(supported, target.effort, minimumEffort(target.role ?? inferRole(target.effort)));
      } catch {
        return undefined;
      }
      const role = target.role ?? inferRole(target.effort);
      const traits = modelTraits(id);
      const fit = role === "planner" || role === "reviewer" ? traits.reasoningFit : traits.executionFit;
      const downgrade = EFFORT_ORDER.indexOf(target.effort) - EFFORT_ORDER.indexOf(effort);
      const currentBonus = target.currentModel && entryName.includes(target.currentModel.toLowerCase()) ? 4 : 0;
      return {
        entry,
        id,
        effort,
        score: fit * 100 - traits.costTier * 10 - downgrade * 8 + currentBonus,
      };
    })
    .filter((candidate): candidate is ModelCandidate => candidate !== undefined);

  return candidates.sort((left, right) =>
    right.score - left.score ||
    left.id.toLowerCase().localeCompare(right.id.toLowerCase()),
  );
}

function modelFamily(requested: string): ModelFamily | undefined {
  const normalized = requested.toLowerCase();
  if (normalized === "luna" || normalized.includes("luna")) return "luna";
  if (normalized === "sol" || normalized.includes("sol")) return "sol";
  return undefined;
}

function isUnsupportedModelError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return /unsupported[\s_-]+model/i.test(message);
}

function inferRole(effort: ReasoningEffort): ModelRole {
  if (effort === "low") return "classifier";
  if (effort === "xhigh" || effort === "ultra") return "planner";
  return "executor";
}

function minimumEffort(role: ModelRole): ReasoningEffort {
  switch (role) {
    case "planner":
    case "reviewer":
      return "high";
    case "classifier":
      return "low";
    case "executor":
      return "high";
  }
}

function modelTraits(modelId: string): {
  costTier: number;
  reasoningFit: number;
  executionFit: number;
} {
  const name = modelId.toLowerCase();
  const cheap = /(mini|nano|flash|haiku|luna|fast|small)/.test(name);
  const reasoning = /(sol|reason|opus|o[1345](?:[-.]|$)|pro|think)/.test(name);
  const balanced = /(terra|sonnet|gpt-5\.[456]|gpt-4)/.test(name);
  return {
    costTier: cheap ? 0 : reasoning ? 2 : balanced ? 1 : 1,
    reasoningFit: reasoning ? 3 : balanced ? 2 : 1,
    executionFit: cheap ? 3 : balanced ? 2 : reasoning ? 1 : 2,
  };
}

function resolveEffort(
  supported: ReasoningEffort[],
  requested: ReasoningEffort,
  minimum: ReasoningEffort = "low",
): ReasoningEffort {
  if (
    supported.includes(requested) &&
    EFFORT_ORDER.indexOf(requested) >= EFFORT_ORDER.indexOf(minimum)
  ) {
    return requested;
  }
  const requestedIndex = EFFORT_ORDER.indexOf(requested);
  const fallback = [...supported]
    .filter((effort) => EFFORT_ORDER.indexOf(effort) < requestedIndex)
    .sort((left, right) => EFFORT_ORDER.indexOf(right) - EFFORT_ORDER.indexOf(left))[0];
  if (!fallback || EFFORT_ORDER.indexOf(fallback) < EFFORT_ORDER.indexOf(minimum)) {
    throw new ModelPreflightError(`Requested effort is unavailable: ${requested}`);
  }
  return fallback;
}

function readThreadId(value: unknown): string | undefined {
  if (!isRecord(value)) return undefined;
  const thread = value.thread;
  if (isRecord(thread) && typeof thread.id === "string") return thread.id;
  return typeof value.threadId === "string" ? value.threadId : undefined;
}

function readThreadSettingsUpdated(value: unknown): ThreadSettingsUpdatedParams | undefined {
  if (!isRecord(value)) return undefined;
  const result: ThreadSettingsUpdatedParams = {};
  if (typeof value.threadId === "string") result.threadId = value.threadId;
  if (isRecord(value.threadSettings)) {
    const settings: { model?: string; effort?: string | null } = {};
    if (typeof value.threadSettings.model === "string") settings.model = value.threadSettings.model;
    if (typeof value.threadSettings.effort === "string" || value.threadSettings.effort === null) {
      settings.effort = value.threadSettings.effort;
    }
    result.threadSettings = settings;
  }
  return result;
}

function matchesTurn(value: unknown, threadId: string, turnId: string): boolean {
  const completed = readTurnCompleted(value);
  return completed?.threadId === threadId && completed.turn?.id === turnId;
}

function readTurnCompleted(value: unknown): TurnCompletedParams | undefined {
  if (!isRecord(value)) return undefined;
  const result: TurnCompletedParams = {};
  if (typeof value.threadId === "string") result.threadId = value.threadId;
  if (isRecord(value.turn)) {
    const turn: Turn = {};
    if (typeof value.turn.id === "string") turn.id = value.turn.id;
    if (typeof value.turn.status === "string") turn.status = value.turn.status;
    if (isRecord(value.turn.error)) {
      const error: { message?: string } = {};
      if (typeof value.turn.error.message === "string") error.message = value.turn.error.message;
      turn.error = error;
    } else if (value.turn.error === null) {
      turn.error = null;
    }
    if (Array.isArray(value.turn.items)) {
      turn.items = value.turn.items.filter(isRecord).map((item) => {
        const parsed: { type?: string; text?: string } = {};
        if (typeof item.type === "string") parsed.type = item.type;
        if (typeof item.text === "string") parsed.text = item.text;
        return parsed;
      });
    }
    result.turn = turn;
  }
  return result;
}

function extractTurnText(turn: Turn, notifications: Array<{ method: string; params?: unknown }>): string {
  const texts = (turn.items ?? [])
    .filter((item) => item.type === "agentMessage" && typeof item.text === "string")
    .map((item) => item.text as string);
  for (const notification of notifications) {
    if (notification.method === "item/completed" && isRecord(notification.params)) {
      const item = notification.params.item;
      if (isRecord(item) && item.type === "agentMessage" && typeof item.text === "string") {
        texts.push(item.text);
      }
    }
    if (notification.method === "item/agentMessage/delta" && isRecord(notification.params)) {
      if (typeof notification.params.delta === "string") texts.push(notification.params.delta);
    }
  }
  return texts
    .join("\n")
    .trim();
}

function combineSignals(...signals: Array<AbortSignal | undefined>): AbortSignal {
  const controller = new AbortController();
  const abort = () => controller.abort();
  for (const signal of signals) {
    if (!signal) continue;
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", abort, { once: true });
  }
  return controller.signal;
}

async function terminateChild(child: ChildProcessWithoutNullStreams, graceMs: number): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) return;
  child.kill("SIGTERM");
  await new Promise<void>((resolve) => {
    const timer = setTimeout(() => {
      if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL");
      resolve();
    }, graceMs);
    child.once("close", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}
