#!/usr/bin/env node

// src/hook.ts
import process2 from "node:process";

// src/config.ts
import { readdirSync } from "node:fs";
import os from "node:os";
import path from "node:path";
var PLUGIN_NAME = "semantic-model-router";
var PROMPT_TTL_MS = 10 * 60 * 1e3;
var RouterConfigError = class extends Error {
  constructor(message) {
    super(message);
    this.name = "RouterConfigError";
  }
};
function routerDataDir(env = process.env, cwd = process.cwd()) {
  const configured = env.SEMANTIC_ROUTER_DATA_DIR ?? env.PLUGIN_DATA ?? env.CLAUDE_PLUGIN_DATA;
  if (configured?.trim()) return path.resolve(configured);
  const codexHome = path.resolve(env.CODEX_HOME ?? path.join(os.homedir(), ".codex"));
  const marketplace = marketplaceFromPluginCache(cwd);
  if (marketplace) {
    return path.join(codexHome, "plugins", "data", `${PLUGIN_NAME}-${marketplace}`);
  }
  const dataRoot = path.join(codexHome, "plugins", "data");
  try {
    const candidates = readdirSync(dataRoot, { withFileTypes: true }).filter(
      (entry) => entry.isDirectory() && entry.name.startsWith(`${PLUGIN_NAME}-`)
    );
    if (candidates.length === 1 && candidates[0]) {
      return path.join(dataRoot, candidates[0].name);
    }
  } catch {
  }
  throw new RouterConfigError("Router data directory is unavailable");
}
function marketplaceFromPluginCache(cwd) {
  const parts = path.resolve(cwd).split(path.sep);
  for (let index = 0; index < parts.length - 3; index += 1) {
    if (parts[index] !== "plugins" || parts[index + 1] !== "cache") continue;
    const marketplace = parts[index + 2];
    const plugin = parts[index + 3];
    if (plugin === PLUGIN_NAME && marketplace && /^[A-Za-z0-9._-]+$/.test(marketplace)) {
      return marketplace;
    }
  }
  return void 0;
}

// src/routing/hard-rules.ts
var RULES = [
  [
    "destructive",
    /(?:\b(?:delete|remove|drop|truncate|overwrite|reset\s+--hard|rm\s+-rf)\b|删除|清空|覆盖|硬重置)/i
  ],
  [
    "external_side_effect",
    /(?:\b(?:publish|deploy|push|send|email|message|charge|refund)\b|发布|部署|推送|发送|付款|扣款|退款)/i
  ],
  [
    "permission_or_security",
    /(?:\b(?:permission|authorization|authentication|tenant|security|access control)\b|权限|鉴权|认证|租户|安全)/i
  ],
  [
    "schema_or_migration",
    /(?:\b(?:schema|migration|migrate|database structure)\b|数据库结构|数据迁移|表结构)/i
  ],
  [
    "credential_handling",
    /(?:\b(?:api[_ -]?key|secret|password|credential|token)\b|密钥|密码|凭证|令牌)/i
  ]
];
function detectRiskTags(prompt) {
  return RULES.filter(([, pattern]) => pattern.test(prompt)).map(([tag]) => tag);
}

// src/routing/overrides.ts
var COMMAND = /^\s*@(sol|luna|current|auto-off|auto-on|approve|reject|route-good|route-bad|delete)(?:\s+([A-Za-z0-9_-]{1,128}))?(?:\s+([A-Za-z0-9_-]{1,128}))?(?=\s|$)/i;
function parseControlCommand(prompt) {
  const match = COMMAND.exec(prompt);
  if (!match) return { kind: "none" };
  const name = match[1]?.toLowerCase();
  const taskId = match[2];
  const approvalToken = match[3];
  switch (name) {
    case "sol":
      return { kind: "route", route: "S" };
    case "luna":
      return { kind: "route", route: "L" };
    case "current":
      return { kind: "current" };
    case "auto-off":
      return { kind: "auto", enabled: false };
    case "auto-on":
      return { kind: "auto", enabled: true };
    case "approve":
    case "reject":
      return taskId ? {
        kind: "approval",
        action: name,
        taskId,
        ...approvalToken ? { approvalToken } : {}
      } : { kind: "approval", action: name };
    case "route-good":
    case "route-bad": {
      const label = name === "route-good" ? "correct" : "incorrect";
      return taskId ? { kind: "feedback", label, taskId } : { kind: "feedback", label };
    }
    case "delete":
      return taskId ? { kind: "delete", taskId } : { kind: "delete" };
    default:
      return { kind: "none" };
  }
}
function routeOverride(command) {
  return command.kind === "route" ? command.route : void 0;
}

// src/storage/prompt-spool.ts
import { createHash, randomUUID } from "node:crypto";
import { constants } from "node:fs";
import {
  chmod,
  lstat,
  mkdir,
  open,
  readdir,
  readFile,
  rm
} from "node:fs/promises";
import path2 from "node:path";
var REFERENCE_PATTERN = /^[a-f0-9]{16}\.[a-f0-9-]{36}$/;
var PromptReferenceError = class extends Error {
  constructor(message) {
    super(message);
    this.name = "PromptReferenceError";
  }
};
function hash(value, length = 16) {
  return createHash("sha256").update(value).digest("hex").slice(0, length);
}
function spoolDir(dataDir) {
  return path2.join(dataDir, "spool");
}
function promptPath(dataDir, reference) {
  if (!REFERENCE_PATTERN.test(reference)) {
    throw new PromptReferenceError("Prompt reference is invalid");
  }
  return path2.join(spoolDir(dataDir), `${reference}.json`);
}
async function ensurePrivateDirectory(directory) {
  await mkdir(directory, { recursive: true, mode: 448 });
  await chmod(directory, 448);
}
async function createPromptReference(dataDir, input, now = Date.now()) {
  await cleanupExpiredPrompts(dataDir, now);
  const directory = spoolDir(dataDir);
  await ensurePrivateDirectory(directory);
  const reference = `${hash(`${input.sessionId}\0${input.turnId}`)}.${randomUUID()}`;
  const filePath = promptPath(dataDir, reference);
  const envelope = {
    version: 1,
    createdAt: new Date(now).toISOString(),
    expiresAt: new Date(now + PROMPT_TTL_MS).toISOString(),
    sessionKey: hash(input.sessionId, 24),
    turnKey: hash(input.turnId, 24),
    prompt: input.prompt,
    riskTags: input.riskTags ?? []
  };
  if (input.cwd !== void 0) envelope.cwd = input.cwd;
  if (input.model !== void 0) envelope.model = input.model;
  if (input.permissionMode !== void 0) envelope.permissionMode = input.permissionMode;
  if (input.override !== void 0) envelope.override = input.override;
  const handle = await open(
    filePath,
    constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL,
    384
  );
  try {
    await handle.writeFile(JSON.stringify(envelope), "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
  await chmod(filePath, 384);
  return reference;
}
async function cleanupExpiredPrompts(dataDir, now = Date.now()) {
  const directory = spoolDir(dataDir);
  let names;
  try {
    names = await readdir(directory);
  } catch {
    return 0;
  }
  let removed = 0;
  for (const name of names) {
    if (!name.endsWith(".json")) continue;
    const filePath = path2.join(directory, name);
    try {
      const stats = await lstat(filePath);
      if (stats.isSymbolicLink() || !stats.isFile() || stats.mtimeMs + PROMPT_TTL_MS <= now) {
        await rm(filePath, { force: true });
        removed += 1;
      }
    } catch {
    }
  }
  return removed;
}

// src/storage/session-state.ts
import { createHash as createHash2 } from "node:crypto";
import { chmod as chmod2, mkdir as mkdir2, readFile as readFile2, rename, writeFile } from "node:fs/promises";
import path3 from "node:path";
function stateKey(sessionId) {
  return createHash2("sha256").update(sessionId).digest("hex").slice(0, 32);
}
function statePath(dataDir, sessionId) {
  return path3.join(dataDir, "sessions", `${stateKey(sessionId)}.json`);
}
async function isAutoRoutingEnabled(dataDir, sessionId) {
  try {
    const value = JSON.parse(await readFile2(statePath(dataDir, sessionId), "utf8"));
    return value.enabled !== false;
  } catch {
    return true;
  }
}
async function setAutoRouting(dataDir, sessionId, enabled) {
  const directory = path3.join(dataDir, "sessions");
  await mkdir2(directory, { recursive: true, mode: 448 });
  await chmod2(directory, 448);
  const target = statePath(dataDir, sessionId);
  const temporary = `${target}.${process.pid}.tmp`;
  await writeFile(
    temporary,
    JSON.stringify({ enabled, updatedAt: (/* @__PURE__ */ new Date()).toISOString() }),
    { encoding: "utf8", mode: 384 }
  );
  await chmod2(temporary, 384);
  await rename(temporary, target);
}

// src/hook.ts
var MAX_HOOK_INPUT_BYTES = 16 * 1024 * 1024;
function emitContext(additionalContext) {
  process2.stdout.write(
    JSON.stringify({
      continue: true,
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext
      }
    })
  );
}
async function readHookInput() {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of process2.stdin) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    bytes += buffer.length;
    if (bytes > MAX_HOOK_INPUT_BYTES) {
      throw new Error("Hook input exceeds private spool limit");
    }
    chunks.push(buffer);
  }
  const value = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if (!isHookInput(value)) throw new Error("Hook input is incomplete");
  return value;
}
function isHookInput(value) {
  if (!value || typeof value !== "object") return false;
  const input = value;
  return typeof input.prompt === "string" && typeof input.session_id === "string" && typeof input.turn_id === "string";
}
async function main() {
  if (process2.env.SEMANTIC_ROUTER_CHILD === "1") return;
  const input = await readHookInput();
  const command = parseControlCommand(input.prompt);
  if (command.kind === "current") return;
  const dataDir = routerDataDir();
  if (command.kind === "auto") {
    await setAutoRouting(dataDir, input.session_id, command.enabled);
    emitContext(
      command.enabled ? "Semantic Model Router enabled for this session. Handle this control command with the current model; no route tool call is needed." : "Semantic Model Router disabled for this session. Handle this control command with the current model; use @auto-on to enable it."
    );
    return;
  }
  if (command.kind === "approval") {
    if (!command.taskId) {
      emitContext("Semantic Model Router needs task_id for approval control. Do not execute or claim approval.");
      return;
    }
    if (command.action === "approve" && !command.approvalToken) {
      emitContext(`Call MCP approve_task with task_id "${command.taskId}" and approval_token from route receipt. Do not execute before tool result.`);
      return;
    }
    if (command.action === "approve") {
      emitContext(
        `Call MCP approve_task exactly once with task_id "${command.taskId}" and approval_token "${command.approvalToken}". Do not execute or claim completion before tool result.`
      );
      return;
    }
    emitContext(
      `Call MCP reject_task exactly once with task_id "${command.taskId}". Rejection performs no business action; do not claim execution.`
    );
    return;
  }
  if (command.kind === "feedback") {
    if (!command.taskId) {
      emitContext("Semantic Model Router needs task_id for feedback control. Do not claim feedback was recorded.");
      return;
    }
    emitContext(
      `Call MCP submit_route_feedback exactly once with task_id "${command.taskId}" and label "${command.label}". This is weak feedback unless explicit confirmation=true is supplied.`
    );
    return;
  }
  if (command.kind === "delete") {
    if (!command.taskId) {
      emitContext("Semantic Model Router needs task_id for deletion control. Do not delete repository data.");
      return;
    }
    emitContext(
      `Call MCP delete_task exactly once with task_id "${command.taskId}" and confirmation "DELETE_TASK". This deletes only local route metadata.`
    );
    return;
  }
  if (!await isAutoRoutingEnabled(dataDir, input.session_id)) return;
  const override = routeOverride(command);
  const promptRef = await createPromptReference(dataDir, {
    prompt: input.prompt,
    sessionId: input.session_id,
    turnId: input.turn_id,
    ...typeof input.cwd === "string" ? { cwd: input.cwd } : {},
    ...typeof input.model === "string" ? { model: input.model } : {},
    ...typeof input.permission_mode === "string" ? { permissionMode: input.permission_mode } : {},
    ...override ? { override } : {},
    riskTags: detectRiskTags(input.prompt)
  });
  emitContext(
    `Semantic Model Router Phase 6: before other work, call MCP tool route_task exactly once with prompt_ref "${promptRef}". Treat it as opaque and never quote or persist it. The tool returns a bounded route receipt and workflow result; do not claim a model role ran unless the receipt says so.`
  );
}
main().catch(() => {
  emitContext(
    "Route: degraded-current | semantic router control plane unavailable | current model retained. Do not claim Sol or Luna ran."
  );
});
