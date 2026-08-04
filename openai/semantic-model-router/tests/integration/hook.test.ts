import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, readdir } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { consumePromptReference } from "../../src/storage/prompt-spool.js";

const hookPath = path.resolve("hooks/user-prompt-submit.mjs");

async function runHook(
  dataDir: string,
  prompt: string,
  extraEnv: Record<string, string> = {},
): Promise<{ stdout: string; stderr: string; code: number | null }> {
  const child = spawn(process.execPath, [hookPath], {
    env: {
      ...process.env,
      SEMANTIC_ROUTER_DATA_DIR: dataDir,
      ...extraEnv,
    },
    stdio: ["pipe", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8").on("data", (chunk) => (stdout += chunk));
  child.stderr.setEncoding("utf8").on("data", (chunk) => (stderr += chunk));
  child.stdin.end(
    JSON.stringify({
      hook_event_name: "UserPromptSubmit",
      prompt,
      session_id: "session-hook",
      turn_id: `turn-${Math.random()}`,
      cwd: "/private/repository",
      model: "current-model",
      permission_mode: "default",
    }),
  );
  const code = await new Promise<number | null>((resolve) =>
    child.on("close", resolve),
  );
  return { stdout, stderr, code };
}

test("hook emits only opaque reference and child/current bypass emit nothing", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-hook-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });
  const secretPrompt = "analyze credential token=private-hook-secret";
  const routed = await runHook(root, secretPrompt);

  assert.equal(routed.code, 0);
  assert.equal(routed.stderr, "");
  assert.equal(routed.stdout.includes(secretPrompt), false);
  assert.equal(routed.stdout.includes("private-hook-secret"), false);
  const output = JSON.parse(routed.stdout);
  const context = output.hookSpecificOutput.additionalContext as string;
  const reference = /prompt_ref \"([^\"]+)\"/.exec(context)?.[1];
  assert.ok(reference);
  const envelope = await consumePromptReference(root, reference);
  assert.equal(envelope.prompt, secretPrompt);
  assert.deepEqual(await readdir(path.join(root, "spool")), []);

  assert.equal((await runHook(root, "@current do work")).stdout, "");
  assert.equal(
    (await runHook(root, "child work", { SEMANTIC_ROUTER_CHILD: "1" })).stdout,
    "",
  );
});

test("auto-off bypasses until auto-on", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-auto-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });

  assert.match((await runHook(root, "@auto-off")).stdout, /disabled/);
  assert.equal((await runHook(root, "do not route this")).stdout, "");
  assert.match((await runHook(root, "@auto-on")).stdout, /enabled/);
  assert.match((await runHook(root, "route this")).stdout, /prompt_ref/);
});
