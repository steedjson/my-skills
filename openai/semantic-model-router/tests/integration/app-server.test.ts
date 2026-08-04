import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import test from "node:test";

import {
  AppServerSupervisor,
  ModelPreflightError,
  resolveRoleTarget,
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

test("preflights exact settings without requiring settings notification", async (t) => {
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
    const initialize = requests.find((request) => request.method === "initialize");
    assert.equal(initialize.params.capabilities.experimentalApi, true);
    const threadStart = requests.find((request) => request.method === "thread/start");
    assert.equal(threadStart.params.model, target.model);
    assert.equal(threadStart.params.allowProviderModelFallback, false);
    const settings = requests.find((request) => request.method === "thread/settings/update");
    assert.equal(settings.params.model, target.model);
    assert.equal(settings.params.effort, target.effort);
  }
});

test("resolves installed model suffixes and downgrades unsupported max to highest available effort", () => {
  const resolved = resolveRoleTarget(
    [
      {
        id: "gpt-5.6-luna-csap-codexbuy-oai",
        model: "gpt-5.6-luna-csap-codexbuy-oai",
        supportedReasoningEfforts: [
          { reasoningEffort: "low" },
          { reasoningEffort: "xhigh" },
        ],
      },
    ],
    lunaMax,
  );
  assert.equal(resolved.model, "gpt-5.6-luna-csap-codexbuy-oai");
  assert.equal(resolved.effort, "xhigh");
  assert.equal(
    resolved.selectionReason,
    "requested=gpt-5.6-luna | role=executor | model=gpt-5.6-luna-csap-codexbuy-oai | requested-effort=max -> resolved-effort=xhigh",
  );
});

test("auto route falls back when provider rejects top-ranked model", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-model-fallback-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });
  const log = path.join(root, "fallback.jsonl");
  const rejected = "deepseek-v4-flash-0731";
  const fallback = "gpt-5.6-luna-csap-codexbuy-oai";
  const models = [
    {
      id: rejected,
      supportedReasoningEfforts: [{ reasoningEffort: "high" }, { reasoningEffort: "max" }],
    },
    {
      id: fallback,
      supportedReasoningEfforts: [{ reasoningEffort: "low" }, { reasoningEffort: "high" }, { reasoningEffort: "max" }],
    },
    {
      id: "gpt-5.6-sol-csap-codexbuy-oai",
      supportedReasoningEfforts: [{ reasoningEffort: "high" }, { reasoningEffort: "xhigh" }],
    },
  ];
  const result = await supervisor({
    FAKE_APP_SERVER_LOG: log,
    FAKE_APP_SERVER_MODELS: JSON.stringify(models),
    FAKE_APP_SERVER_UNSUPPORTED_MODEL: rejected,
  }).runTurn("execute this", {
    model: "auto",
    effort: "max",
    role: "executor",
    sandbox: "read-only",
  });
  assert.equal(result.model, fallback);
  assert.equal(result.effort, "max");
  const requests = (await readFile(log, "utf8")).trim().split("\n").map((line) => JSON.parse(line));
  assert.deepEqual(
    requests.filter((request) => request.method === "thread/start").map((request) => request.params.model),
    [rejected, fallback],
  );
});

test("auto selection prefers role-fit models and keeps deterministic tie-breaks", () => {
  const models = [
    {
      id: "gpt-5.6-luna-csap-codexbuy-oai",
      supportedReasoningEfforts: [
        { reasoningEffort: "low" },
        { reasoningEffort: "medium" },
        { reasoningEffort: "high" },
        { reasoningEffort: "xhigh" },
        { reasoningEffort: "max" },
      ],
    },
    {
      id: "gpt-5.6-sol-csap-codexbuy-oai",
      supportedReasoningEfforts: [{ reasoningEffort: "high" }, { reasoningEffort: "xhigh" }],
    },
    {
      id: "gpt-5.6-terra-csap-codexbuy-oai",
      supportedReasoningEfforts: [{ reasoningEffort: "low" }, { reasoningEffort: "high" }],
    },
  ];
  assert.equal(
    resolveRoleTarget(models, {
      model: "auto",
      role: "classifier",
      effort: "low",
      sandbox: "read-only",
    }).model,
    "gpt-5.6-luna-csap-codexbuy-oai",
  );
  assert.equal(
    resolveRoleTarget(models, {
      model: "auto",
      role: "planner",
      effort: "xhigh",
      sandbox: "read-only",
    }).model,
    "gpt-5.6-sol-csap-codexbuy-oai",
  );
  assert.equal(
    resolveRoleTarget(models, {
      model: "auto",
      role: "executor",
      effort: "max",
      sandbox: "read-only",
    }).model,
    "gpt-5.6-luna-csap-codexbuy-oai",
  );
  assert.equal(
    resolveRoleTarget(models, {
      model: "auto",
      role: "reviewer",
      effort: "xhigh",
      sandbox: "read-only",
    }).model,
    "gpt-5.6-sol-csap-codexbuy-oai",
  );
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
