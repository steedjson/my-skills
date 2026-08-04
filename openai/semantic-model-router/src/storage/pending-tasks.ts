import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import {
  chmod,
  lstat,
  mkdir,
  readFile,
  readdir,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

import { PROMPT_TTL_MS } from "../config.js";
import { redactText } from "../security/redaction.js";
import type { RouteOverride } from "../routing/overrides.js";
import type { RiskTag } from "../routing/hard-rules.js";
import type { PromptEnvelope } from "./prompt-spool.js";

const TASK_ID_PATTERN = /^task-[A-Za-z0-9_-]{8,128}$/;
const TOKEN_PATTERN = /^approval-[A-Za-z0-9_-]{8,128}$/;
const MAX_TASK_PROMPT = 8_000;
const taskLocks = new Map<string, Promise<void>>();

export type PendingTaskState =
  | "awaiting_approval"
  | "approved"
  | "rejected"
  | "expired"
  | "completed";

export interface PendingTaskRecord {
  version: 1;
  taskId: string;
  state: PendingTaskState;
  createdAt: string;
  expiresAt: string;
  sessionKey: string;
  turnKey: string;
  repoKey: string;
  taskPrompt: string;
  permissionMode?: string;
  override?: RouteOverride;
  riskTags: RiskTag[];
  approvalTokenHash: string;
  approvedAt?: string;
  rejectedAt?: string;
  completedAt?: string;
}

export interface PendingTaskCreated {
  taskId: string;
  approvalToken: string;
  record: PendingTaskRecord;
}

export interface RouteFeedbackRecord {
  version: 1;
  taskId: string;
  label: "correct" | "incorrect";
  strength: "weak" | "strong";
  createdAt: string;
  comment?: string;
}

export class PendingTaskError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PendingTaskError";
  }
}

function hash(value: string, length = 24): string {
  return createHash("sha256").update(value).digest("hex").slice(0, length);
}

export function repoKeyFromCwd(cwd?: string): string {
  return hash(cwd?.trim() || "unknown-repository", 24);
}

function pendingDir(dataDir: string): string {
  return path.join(dataDir, "pending");
}

function feedbackDir(dataDir: string): string {
  return path.join(dataDir, "feedback");
}

function safeTaskId(taskId: string): string {
  if (!TASK_ID_PATTERN.test(taskId)) throw new PendingTaskError("Task id is invalid");
  return taskId;
}

function taskPath(dataDir: string, taskId: string): string {
  return path.join(pendingDir(dataDir), `${safeTaskId(taskId)}.json`);
}

async function ensurePrivateDirectory(directory: string): Promise<void> {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  await chmod(directory, 0o700);
}

async function writePrivateJson(filePath: string, value: unknown): Promise<void> {
  await ensurePrivateDirectory(path.dirname(filePath));
  const temporary = `${filePath}.${process.pid}.${randomUUID()}.tmp`;
  await writeFile(temporary, JSON.stringify(value), { encoding: "utf8", mode: 0o600 });
  await chmod(temporary, 0o600);
  await rename(temporary, filePath);
  await chmod(filePath, 0o600);
}

async function readTask(dataDir: string, taskId: string, now = Date.now()): Promise<PendingTaskRecord> {
  const filePath = taskPath(dataDir, taskId);
  let raw: string;
  try {
    const stats = await lstat(filePath);
    if (!stats.isFile() || stats.isSymbolicLink()) throw new PendingTaskError("Task record is not a private file");
    raw = await readFile(filePath, "utf8");
  } catch (error) {
    if (error instanceof PendingTaskError) throw error;
    throw new PendingTaskError("Task is missing, expired, or already consumed");
  }
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new PendingTaskError("Task record is invalid");
  }
  if (!isPendingTaskRecord(value)) throw new PendingTaskError("Task record is invalid");
  if (Date.parse(value.expiresAt) <= now && value.state === "awaiting_approval") {
    await markTaskState(dataDir, value, "expired", now);
    throw new PendingTaskError("Task approval expired");
  }
  return value;
}

async function markTaskState(
  dataDir: string,
  record: PendingTaskRecord,
  state: PendingTaskState,
  now = Date.now(),
): Promise<PendingTaskRecord> {
  const updated: PendingTaskRecord = { ...record, state };
  if (state === "approved") updated.approvedAt = new Date(now).toISOString();
  if (state === "rejected") updated.rejectedAt = new Date(now).toISOString();
  if (state === "completed") updated.completedAt = new Date(now).toISOString();
  await writePrivateJson(taskPath(dataDir, record.taskId), updated);
  return updated;
}

export async function createPendingTask(
  dataDir: string,
  envelope: PromptEnvelope,
  riskTags: RiskTag[],
  now = Date.now(),
): Promise<PendingTaskCreated> {
  await cleanupPendingTasks(dataDir, now);
  const taskId = `task-${randomUUID()}`;
  const approvalToken = `approval-${randomUUID()}`;
  const record: PendingTaskRecord = {
    version: 1,
    taskId,
    state: "awaiting_approval",
    createdAt: new Date(now).toISOString(),
    expiresAt: new Date(now + PROMPT_TTL_MS).toISOString(),
    sessionKey: envelope.sessionKey,
    turnKey: envelope.turnKey,
    repoKey: repoKeyFromCwd(envelope.cwd),
    taskPrompt: redactText(envelope.prompt).replace(/[\r\n]+/g, " ").slice(0, MAX_TASK_PROMPT),
    riskTags: [...new Set(riskTags)],
    approvalTokenHash: hash(approvalToken, 64),
  };
  if (envelope.permissionMode !== undefined) record.permissionMode = envelope.permissionMode;
  if (envelope.override !== undefined) record.override = envelope.override;
  await writePrivateJson(taskPath(dataDir, taskId), record);
  return { taskId, approvalToken, record };
}

export async function approvePendingTask(
  dataDir: string,
  taskId: string,
  approvalToken: string,
  now = Date.now(),
): Promise<PendingTaskRecord> {
  if (!TOKEN_PATTERN.test(approvalToken)) throw new PendingTaskError("Approval token is invalid");
  return withTaskLock(`${dataDir}\0${taskId}`, async () => {
    const record = await readTask(dataDir, taskId, now);
    if (record.state !== "awaiting_approval") throw new PendingTaskError("Task is not awaiting approval");
    const expected = Buffer.from(record.approvalTokenHash, "hex");
    const actual = Buffer.from(hash(approvalToken, 64), "hex");
    if (expected.length !== actual.length || !timingSafeEqual(expected, actual)) {
      throw new PendingTaskError("Approval token is invalid");
    }
    return markTaskState(dataDir, record, "approved", now);
  });
}

export async function rejectPendingTask(
  dataDir: string,
  taskId: string,
  now = Date.now(),
): Promise<PendingTaskRecord> {
  return withTaskLock(`${dataDir}\0${taskId}`, async () => {
    const record = await readTask(dataDir, taskId, now);
    if (record.state !== "awaiting_approval") throw new PendingTaskError("Task is not awaiting approval");
    return markTaskState(dataDir, record, "rejected", now);
  });
}

export async function completePendingTask(
  dataDir: string,
  taskId: string,
  now = Date.now(),
): Promise<PendingTaskRecord> {
  return withTaskLock(`${dataDir}\0${taskId}`, async () => {
    const record = await readTask(dataDir, taskId, now);
    if (record.state !== "approved") throw new PendingTaskError("Task is not approved");
    return markTaskState(dataDir, record, "completed", now);
  });
}

export async function deletePendingTask(dataDir: string, taskId: string): Promise<boolean> {
  return withTaskLock(`${dataDir}\0${taskId}`, async () => {
    const filePath = taskPath(dataDir, taskId);
    try {
      await rm(filePath, { force: false });
      return true;
    } catch {
      return false;
    }
  });
}

export async function cleanupPendingTasks(dataDir: string, now = Date.now()): Promise<number> {
  let names: string[];
  try {
    names = await readdir(pendingDir(dataDir));
  } catch {
    return 0;
  }
  let removed = 0;
  for (const name of names) {
    if (!name.endsWith(".json")) continue;
    const filePath = path.join(pendingDir(dataDir), name);
    try {
      const stats = await lstat(filePath);
      if (!stats.isFile() || stats.isSymbolicLink()) {
        await rm(filePath, { force: true });
        removed += 1;
        continue;
      }
      const value = JSON.parse(await readFile(filePath, "utf8")) as Record<string, unknown>;
      if (typeof value.expiresAt === "string" && Date.parse(value.expiresAt) <= now && value.state === "awaiting_approval") {
        await rm(filePath, { force: true });
        removed += 1;
      }
    } catch {
      // Ignore records concurrently consumed or malformed; read path fails closed.
    }
  }
  return removed;
}

export async function countPendingTasks(dataDir: string, now = Date.now()): Promise<number> {
  await cleanupPendingTasks(dataDir, now);
  try {
    const names = await readdir(pendingDir(dataDir));
    let count = 0;
    for (const name of names) {
      if (!name.endsWith(".json")) continue;
      try {
        const value = JSON.parse(await readFile(path.join(pendingDir(dataDir), name), "utf8")) as Record<string, unknown>;
        if (value.state === "awaiting_approval") count += 1;
      } catch {
        // Ignore malformed records; status must fail closed.
      }
    }
    return count;
  } catch {
    return 0;
  }
}

export async function submitRouteFeedback(
  dataDir: string,
  input: {
    taskId: string;
    label: "correct" | "incorrect";
    confirmation?: boolean;
    comment?: string;
  },
  now = Date.now(),
): Promise<RouteFeedbackRecord> {
  safeTaskId(input.taskId);
  const strength = input.confirmation === true ? "strong" : "weak";
  const record: RouteFeedbackRecord = {
    version: 1,
    taskId: input.taskId,
    label: input.label,
    strength,
    createdAt: new Date(now).toISOString(),
  };
  if (strength === "strong" && input.comment?.trim()) {
    record.comment = redactText(input.comment).replace(/[\r\n]+/g, " ").slice(0, 500);
  }
  const filePath = path.join(feedbackDir(dataDir), `${input.taskId}-${randomUUID()}.json`);
  await writePrivateJson(filePath, record);
  return record;
}

export async function forgetRepositoryData(dataDir: string, repoKey: string): Promise<number> {
  if (!/^[a-f0-9]{24}$/.test(repoKey)) throw new PendingTaskError("Repository id is invalid");
  return removeMatchingRecords(dataDir, repoKey);
}

export async function forgetAllRouteData(dataDir: string, confirmation: string): Promise<number> {
  if (confirmation !== "DELETE_ALL_ROUTE_DATA") throw new PendingTaskError("Explicit deletion confirmation required");
  let removed = 0;
  for (const directory of [pendingDir(dataDir), feedbackDir(dataDir)]) {
    try {
      const names = await readdir(directory);
      for (const name of names) {
        if (!name.endsWith(".json")) continue;
        await rm(path.join(directory, name), { force: true });
        removed += 1;
      }
    } catch {
      // Directory may not exist yet.
    }
  }
  return removed;
}

async function removeMatchingRecords(dataDir: string, repoKey: string): Promise<number> {
  let names: string[];
  try {
    names = await readdir(pendingDir(dataDir));
  } catch {
    return 0;
  }
  let removed = 0;
  for (const name of names) {
    if (!name.endsWith(".json")) continue;
    const filePath = path.join(pendingDir(dataDir), name);
    try {
      const value = JSON.parse(await readFile(filePath, "utf8")) as Record<string, unknown>;
      if (value.repoKey === repoKey) {
        await rm(filePath, { force: true });
        removed += 1;
      }
    } catch {
      // Ignore malformed records.
    }
  }
  return removed;
}

function isPendingTaskRecord(value: unknown): value is PendingTaskRecord {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    item.version === 1 &&
    typeof item.taskId === "string" && TASK_ID_PATTERN.test(item.taskId) &&
    typeof item.state === "string" &&
    typeof item.createdAt === "string" &&
    typeof item.expiresAt === "string" &&
    typeof item.sessionKey === "string" &&
    typeof item.turnKey === "string" &&
    typeof item.repoKey === "string" &&
    typeof item.taskPrompt === "string" &&
    Array.isArray(item.riskTags) &&
    typeof item.approvalTokenHash === "string" && /^[a-f0-9]{64}$/.test(item.approvalTokenHash)
  );
}

async function withTaskLock<T>(key: string, operation: () => Promise<T>): Promise<T> {
  let release!: () => void;
  const next = new Promise<void>((resolve) => {
    release = resolve;
  });
  const previous = taskLocks.get(key) ?? Promise.resolve();
  taskLocks.set(key, next);
  await previous;
  try {
    return await operation();
  } finally {
    release();
    if (taskLocks.get(key) === next) taskLocks.delete(key);
  }
}
