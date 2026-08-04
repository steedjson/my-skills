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

export interface RoleTarget {
  model: string;
  effort: ReasoningEffort;
  sandbox: SandboxMode;
  approvalPolicy?: "untrusted" | "on-request" | "never";
}

export interface AppServerTurnResult {
  model: string;
  effort: ReasoningEffort;
  threadId: string;
  turnId: string;
  status: string;
  text: string;
}

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
      this.assertModel(models, target);
      const threadStart = await client.request<Record<string, unknown>>("thread/start", {
        model: target.model,
        allowProviderModelFallback: false,
        ephemeral: true,
        cwd: this.options.cwd ?? process.cwd(),
        sandbox: target.sandbox,
        approvalPolicy: target.approvalPolicy ?? "never",
      }, combined);
      const threadId = readThreadId(threadStart);
      if (!threadId) throw new AppServerTurnError("App Server did not return a thread id");
      if (typeof threadStart.model === "string" && threadStart.model !== target.model) {
        throw new ModelPreflightError("App Server selected unexpected model");
      }
      await client.request("thread/settings/update", {
        threadId,
        model: target.model,
        effort: target.effort,
      }, combined);
      const settingsMessage = await client.waitForNotification(
        (message) =>
          message.method === "thread/settings/updated" &&
          readThreadSettingsUpdated(message.params)?.threadId === threadId,
        this.options.requestTimeoutMs,
        combined,
      );
      const settings = readThreadSettingsUpdated(settingsMessage.params)?.threadSettings;
      if (settings?.model !== target.model || settings.effort !== target.effort) {
        throw new ModelPreflightError("App Server did not apply exact model settings");
      }
      const turnStart = await client.request<TurnStartResult>("turn/start", {
        threadId,
        input: [{ type: "text", text: prompt }],
      }, combined);
      const turnId = turnStart.turn?.id;
      if (!turnId) throw new AppServerTurnError("App Server did not return a turn id");
      const completedMessage = await client.waitForNotification(
        (message) =>
          message.method === "turn/completed" &&
          matchesTurn(message.params, threadId, turnId),
        this.options.requestTimeoutMs,
        combined,
      );
      const completed = readTurnCompleted(completedMessage.params);
      const turn = completed?.turn;
      if (!turn || turn.status !== "completed") {
        throw new AppServerTurnError(redactText(turn?.error?.message ?? "App Server turn failed"));
      }
      return {
        model: target.model,
        effort: target.effort,
        threadId,
        turnId,
        status: turn.status,
        text: extractTurnText(turn, client.drainNotifications()),
      };
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

  private assertModel(models: ModelListEntry[], target: RoleTarget): void {
    const model = models.find((entry) => entry.id === target.model || entry.model === target.model);
    if (!model) throw new ModelPreflightError(`Requested model is unavailable: ${target.model}`);
    const efforts = model.supportedReasoningEfforts ?? [];
    if (!efforts.some((entry) => entry.reasoningEffort === target.effort)) {
      throw new ModelPreflightError(`Requested effort is unavailable: ${target.model}/${target.effort}`);
    }
  }
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
