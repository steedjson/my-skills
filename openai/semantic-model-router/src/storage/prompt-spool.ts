import { createHash, randomUUID } from "node:crypto";
import { constants } from "node:fs";
import {
  chmod,
  lstat,
  mkdir,
  open,
  readdir,
  readFile,
  rm,
} from "node:fs/promises";
import path from "node:path";

import { PROMPT_TTL_MS } from "../config.js";
import type { RouteOverride } from "../routing/overrides.js";
import type { RiskTag } from "../routing/hard-rules.js";

const REFERENCE_PATTERN = /^[a-f0-9]{16}\.[a-f0-9-]{36}$/;

export interface PromptInput {
  prompt: string;
  sessionId: string;
  turnId: string;
  cwd?: string;
  model?: string;
  permissionMode?: string;
  override?: RouteOverride;
  riskTags?: RiskTag[];
}

export interface PromptEnvelope {
  version: 1;
  createdAt: string;
  expiresAt: string;
  sessionKey: string;
  turnKey: string;
  prompt: string;
  cwd?: string;
  model?: string;
  permissionMode?: string;
  override?: RouteOverride;
  riskTags: RiskTag[];
}

export class PromptReferenceError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PromptReferenceError";
  }
}

function hash(value: string, length = 16): string {
  return createHash("sha256").update(value).digest("hex").slice(0, length);
}

function spoolDir(dataDir: string): string {
  return path.join(dataDir, "spool");
}

function promptPath(dataDir: string, reference: string): string {
  if (!REFERENCE_PATTERN.test(reference)) {
    throw new PromptReferenceError("Prompt reference is invalid");
  }
  return path.join(spoolDir(dataDir), `${reference}.json`);
}

async function ensurePrivateDirectory(directory: string): Promise<void> {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  await chmod(directory, 0o700);
}

export async function createPromptReference(
  dataDir: string,
  input: PromptInput,
  now = Date.now(),
): Promise<string> {
  await cleanupExpiredPrompts(dataDir, now);
  const directory = spoolDir(dataDir);
  await ensurePrivateDirectory(directory);

  const reference = `${hash(`${input.sessionId}\0${input.turnId}`)}.${randomUUID()}`;
  const filePath = promptPath(dataDir, reference);
  const envelope: PromptEnvelope = {
    version: 1,
    createdAt: new Date(now).toISOString(),
    expiresAt: new Date(now + PROMPT_TTL_MS).toISOString(),
    sessionKey: hash(input.sessionId, 24),
    turnKey: hash(input.turnId, 24),
    prompt: input.prompt,
    riskTags: input.riskTags ?? [],
  };
  if (input.cwd !== undefined) envelope.cwd = input.cwd;
  if (input.model !== undefined) envelope.model = input.model;
  if (input.permissionMode !== undefined) envelope.permissionMode = input.permissionMode;
  if (input.override !== undefined) envelope.override = input.override;

  const handle = await open(
    filePath,
    constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL,
    0o600,
  );
  try {
    await handle.writeFile(JSON.stringify(envelope), "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
  await chmod(filePath, 0o600);
  return reference;
}

export async function consumePromptReference(
  dataDir: string,
  reference: string,
  now = Date.now(),
): Promise<PromptEnvelope> {
  const filePath = promptPath(dataDir, reference);
  let raw: string;
  try {
    const stats = await lstat(filePath);
    if (!stats.isFile() || stats.isSymbolicLink()) {
      throw new PromptReferenceError("Prompt reference is not a private file");
    }
    raw = await readFile(filePath, "utf8");
  } catch (error) {
    if (error instanceof PromptReferenceError) throw error;
    throw new PromptReferenceError("Prompt reference is missing or already consumed");
  } finally {
    await rm(filePath, { force: true }).catch(() => undefined);
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new PromptReferenceError("Prompt reference payload is invalid");
  }
  if (!isPromptEnvelope(parsed)) {
    throw new PromptReferenceError("Prompt reference payload is invalid");
  }
  if (Date.parse(parsed.expiresAt) <= now) {
    throw new PromptReferenceError("Prompt reference expired");
  }
  return parsed;
}

export async function cleanupExpiredPrompts(
  dataDir: string,
  now = Date.now(),
): Promise<number> {
  const directory = spoolDir(dataDir);
  let names: string[];
  try {
    names = await readdir(directory);
  } catch {
    return 0;
  }

  let removed = 0;
  for (const name of names) {
    if (!name.endsWith(".json")) continue;
    const filePath = path.join(directory, name);
    try {
      const stats = await lstat(filePath);
      if (stats.isSymbolicLink() || !stats.isFile() || stats.mtimeMs + PROMPT_TTL_MS <= now) {
        await rm(filePath, { force: true });
        removed += 1;
      }
    } catch {
      // Another process may consume the file concurrently.
    }
  }
  return removed;
}

export async function countPendingPrompts(dataDir: string): Promise<number> {
  await cleanupExpiredPrompts(dataDir);
  try {
    const names = await readdir(spoolDir(dataDir));
    return names.filter((name) => name.endsWith(".json")).length;
  } catch {
    return 0;
  }
}

function isPromptEnvelope(value: unknown): value is PromptEnvelope {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    item.version === 1 &&
    typeof item.createdAt === "string" &&
    typeof item.expiresAt === "string" &&
    typeof item.sessionKey === "string" &&
    typeof item.turnKey === "string" &&
    typeof item.prompt === "string" &&
    Array.isArray(item.riskTags)
  );
}
