import process from "node:process";

import { routerDataDir } from "./config.js";
import { detectRiskTags } from "./routing/hard-rules.js";
import { parseControlCommand, routeOverride } from "./routing/overrides.js";
import { createPromptReference } from "./storage/prompt-spool.js";
import {
  isAutoRoutingEnabled,
  setAutoRouting,
} from "./storage/session-state.js";

const MAX_HOOK_INPUT_BYTES = 16 * 1024 * 1024;

interface HookInput {
  prompt: string;
  session_id: string;
  turn_id: string;
  cwd?: string;
  model?: string;
  permission_mode?: string;
}

function emitContext(additionalContext: string): void {
  process.stdout.write(
    JSON.stringify({
      continue: true,
      hookSpecificOutput: {
        hookEventName: "UserPromptSubmit",
        additionalContext,
      },
    }),
  );
}

async function readHookInput(): Promise<HookInput> {
  const chunks: Buffer[] = [];
  let bytes = 0;
  for await (const chunk of process.stdin) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    bytes += buffer.length;
    if (bytes > MAX_HOOK_INPUT_BYTES) {
      throw new Error("Hook input exceeds private spool limit");
    }
    chunks.push(buffer);
  }
  const value: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if (!isHookInput(value)) throw new Error("Hook input is incomplete");
  return value;
}

function isHookInput(value: unknown): value is HookInput {
  if (!value || typeof value !== "object") return false;
  const input = value as Record<string, unknown>;
  return (
    typeof input.prompt === "string" &&
    typeof input.session_id === "string" &&
    typeof input.turn_id === "string"
  );
}

async function main(): Promise<void> {
  if (process.env.SEMANTIC_ROUTER_CHILD === "1") return;

  const input = await readHookInput();
  const command = parseControlCommand(input.prompt);
  if (command.kind === "current") return;

  const dataDir = routerDataDir();
  if (command.kind === "auto") {
    await setAutoRouting(dataDir, input.session_id, command.enabled);
    emitContext(
      command.enabled
        ? "Semantic Model Router enabled for this session. Handle this control command with the current model; no route tool call is needed."
        : "Semantic Model Router disabled for this session. Handle this control command with the current model; use @auto-on to enable it.",
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
        `Call MCP approve_task exactly once with task_id "${command.taskId}" and approval_token "${command.approvalToken}". Do not execute or claim completion before tool result.`,
      );
      return;
    }
    emitContext(
      `Call MCP reject_task exactly once with task_id "${command.taskId}". Rejection performs no business action; do not claim execution.`,
    );
    return;
  }

  if (command.kind === "feedback") {
    if (!command.taskId) {
      emitContext("Semantic Model Router needs task_id for feedback control. Do not claim feedback was recorded.");
      return;
    }
    emitContext(
      `Call MCP submit_route_feedback exactly once with task_id "${command.taskId}" and label "${command.label}". This is weak feedback unless explicit confirmation=true is supplied.`,
    );
    return;
  }

  if (command.kind === "delete") {
    if (!command.taskId) {
      emitContext("Semantic Model Router needs task_id for deletion control. Do not delete repository data.");
      return;
    }
    emitContext(
      `Call MCP delete_task exactly once with task_id "${command.taskId}" and confirmation "DELETE_TASK". This deletes only local route metadata.`,
    );
    return;
  }

  if (!(await isAutoRoutingEnabled(dataDir, input.session_id))) return;

  const override = routeOverride(command);
  const promptRef = await createPromptReference(dataDir, {
    prompt: input.prompt,
    sessionId: input.session_id,
    turnId: input.turn_id,
    ...(typeof input.cwd === "string" ? { cwd: input.cwd } : {}),
    ...(typeof input.model === "string" ? { model: input.model } : {}),
    ...(typeof input.permission_mode === "string"
      ? { permissionMode: input.permission_mode }
      : {}),
    ...(override ? { override } : {}),
    riskTags: detectRiskTags(input.prompt),
  });

  emitContext(
    `Semantic Model Router Phase 6: before other work, call MCP tool route_task exactly once with prompt_ref "${promptRef}". Treat it as opaque and never quote or persist it. The tool returns a bounded route receipt and workflow result; do not claim a model role ran unless the receipt says so.`,
  );
}

main().catch(() => {
  emitContext(
    "Route: degraded-current | semantic router control plane unavailable | current model retained. Do not claim Sol or Luna ran.",
  );
});
