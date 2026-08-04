import assert from "node:assert/strict";
import { mkdtemp, readdir, stat, utimes } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { PROMPT_TTL_MS } from "../../src/config.js";
import {
  cleanupExpiredPrompts,
  consumePromptReference,
  createPromptReference,
} from "../../src/storage/prompt-spool.js";

test("spool files are private, single-use, and deleted after consumption", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-spool-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });

  const prompt = "private prompt token=do-not-log";
  const reference = await createPromptReference(root, {
    prompt,
    sessionId: "session-1",
    turnId: "turn-1",
  });
  const filePath = path.join(root, "spool", `${reference}.json`);
  assert.equal((await stat(filePath)).mode & 0o777, 0o600);

  const envelope = await consumePromptReference(root, reference);
  assert.equal(envelope.prompt, prompt);
  assert.deepEqual(await readdir(path.join(root, "spool")), []);
  await assert.rejects(() => consumePromptReference(root, reference), /already consumed/);
});

test("cleanup removes prompt files after ten minutes", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-retention-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });

  const reference = await createPromptReference(root, {
    prompt: "expires",
    sessionId: "session-2",
    turnId: "turn-2",
  });
  const filePath = path.join(root, "spool", `${reference}.json`);
  const old = new Date(Date.now() - PROMPT_TTL_MS - 1000);
  await utimes(filePath, old, old);

  assert.equal(await cleanupExpiredPrompts(root), 1);
  assert.deepEqual(await readdir(path.join(root, "spool")), []);
});
