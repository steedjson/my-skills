import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import test from "node:test";

import {
  AppServerSupervisor,
  ModelPreflightError,
  type RoleTarget,
} from "../../src/app-server/supervisor.js";

const fixture = path.resolve("tests/fixtures/fake-app-server.mjs");

const lunaLow: RoleTarget = {
  model: "gpt-5.6-luna",
  effort: "low",
  sandbox: "read-only",
};
const lunaMax: RoleTarget = { ...lunaLow, effort: "max" };
const solXhigh: RoleTarget = {
  model: "gpt-5.6-sol",
  effort: "xhigh",
  sandbox: "read-only",
};

function supervisor(env: Record<string, string>, options: { timeoutMs?: number } = {}) {
  return new AppServerSupervisor({
    command: process.execPath,
    args: [fixture],
    env,
    requestTimeoutMs: 2_000,
    timeoutMs: options.timeoutMs ?? 4_000,
    killGraceMs: 500,
  });
}

test("preflights and applies exact Luna low, Luna max, and Sol xhigh settings", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-app-server-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });
  for (const [target, label] of [
    [lunaLow, "luna-low"],
    [lunaMax, "luna-max"],
    [solXhigh, "sol-xhigh"],
  ] as const) {
    const log = path.join(root, `${label}.jsonl`);
    const result = await supervisor({ FAKE_APP_SERVER_LOG: log }).runTurn("classify this", target);
    assert.equal(result.model, target.model);
    assert.equal(result.effort, target.effort);
    assert.equal(result.status, "completed");
    assert.equal(result.text, "fake result");
    const requests = (await readFile(log, "utf8")).trim().split("\n").map((line) => JSON.parse(line));
    const modelList = requests.find((request) => request.method === "model/list");
    assert.deepEqual(modelList.params, { includeHidden: true });
    const threadStart = requests.find((request) => request.method === "thread/start");
    assert.equal(threadStart.params.model, target.model);
    assert.equal(threadStart.params.allowProviderModelFallback, false);
    const settings = requests.find((request) => request.method === "thread/settings/update");
    assert.equal(settings.params.model, target.model);
    assert.equal(settings.params.effort, target.effort);
  }
});

test("unknown model fails closed before thread creation", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-model-preflight-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });
  const log = path.join(root, "unknown.jsonl");
  await assert.rejects(
    supervisor({ FAKE_APP_SERVER_LOG: log }).runTurn("unknown", {
      ...lunaLow,
      model: "gpt-5.6-unknown",
    }),
    ModelPreflightError,
  );
  const requests = (await readFile(log, "utf8")).trim().split("\n").map((line) => JSON.parse(line));
  assert.equal(requests.some((request) => request.method === "thread/start"), false);
});

test("terminates child App Server after failed turn and redacts provider details", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-app-server-failure-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });
  const marker = path.join(root, "terminated");
  await assert.rejects(
    supervisor({ FAKE_APP_SERVER_MARKER: marker, FAKE_APP_SERVER_FAIL: "1" }).runTurn("fail", lunaLow),
    (error: unknown) => {
      assert.match(String(error), /provider|turn failed/i);
      assert.equal(String(error).includes("private.example"), false);
      return true;
    },
  );
  assert.equal(await readFile(marker, "utf8"), "terminated\n");
});

test("terminates child App Server on timeout", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-app-server-timeout-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });
  const marker = path.join(root, "terminated");
  await assert.rejects(
    supervisor({ FAKE_APP_SERVER_MARKER: marker, FAKE_APP_SERVER_HANG: "1" }, { timeoutMs: 150 }).runTurn("hang", lunaLow),
  );
  assert.equal(await readFile(marker, "utf8"), "terminated\n");
});

test("terminates child App Server when caller cancels", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-app-server-cancel-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });
  const marker = path.join(root, "terminated");
  const controller = new AbortController();
  const pending = supervisor({ FAKE_APP_SERVER_MARKER: marker, FAKE_APP_SERVER_HANG: "1" }).runTurn(
    "cancel",
    lunaLow,
    controller.signal,
  );
  setTimeout(() => controller.abort(), 100);
  await assert.rejects(pending, /cancel|closed|timed out/i);
  assert.equal(await readFile(marker, "utf8"), "terminated\n");
});
