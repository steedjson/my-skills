import assert from "node:assert/strict";
import { mkdtemp, readdir } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

import { createPromptReference } from "../../src/storage/prompt-spool.js";

const fakeAppServer = path.resolve("tests/fixtures/fake-app-server.mjs");

test("MCP initializes, reports status, and consumes prompt without echoing it", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-mcp-"));
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [path.resolve("dist/server.js")],
    cwd: process.cwd(),
    env: {
      PATH: process.env.PATH ?? "",
      SEMANTIC_ROUTER_DATA_DIR: root,
      SEMANTIC_ROUTER_APP_SERVER_COMMAND: process.execPath,
      SEMANTIC_ROUTER_APP_SERVER_ARGS: JSON.stringify([fakeAppServer]),
    },
    stderr: "pipe",
  });
  const client = new Client({ name: "semantic-router-test", version: "1.0.0" });
  t.after(async () => {
    await client.close().catch(() => undefined);
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });

  await client.connect(transport);
  const tools = await client.listTools();
  assert.deepEqual(
    tools.tools.map((tool) => tool.name).sort(),
    [
      "activate_policy_candidate",
      "approve_task",
      "create_policy_candidate",
      "delete_task",
      "forget_all_route_data",
      "forget_repo_data",
      "get_router_status",
      "reject_task",
      "review_policy_candidate",
      "rollback_policy",
      "route_task",
      "run_route_maintenance",
      "run_route_retention",
      "submit_route_feedback",
    ],
  );

  const status = await client.callTool({ name: "get_router_status", arguments: {} });
  assert.match(JSON.stringify(status), /phase-6-maintenance/);

  const rawPrompt = "private MCP prompt";
  const reference = await createPromptReference(root, {
    prompt: rawPrompt,
    sessionId: "session-mcp",
    turnId: "turn-mcp",
    override: "L",
    riskTags: [],
  });
  const result = await client.callTool({
    name: "route_task",
    arguments: { prompt_ref: reference },
  });
  const serialized = JSON.stringify(result);
  assert.match(serialized, /Route: L/);
  assert.equal(serialized.includes(rawPrompt), false);
  assert.deepEqual(await readdir(path.join(root, "spool")), []);
});

test("MCP durable approval creates no executor before approval and resumes with token", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-approval-"));
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [path.resolve("dist/server.js")],
    cwd: process.cwd(),
    env: {
      PATH: process.env.PATH ?? "",
      SEMANTIC_ROUTER_DATA_DIR: root,
      SEMANTIC_ROUTER_APP_SERVER_COMMAND: process.execPath,
      SEMANTIC_ROUTER_APP_SERVER_ARGS: JSON.stringify([fakeAppServer]),
    },
    stderr: "pipe",
  });
  const client = new Client({ name: "semantic-router-approval-test", version: "1.0.0" });
  t.after(async () => {
    await client.close().catch(() => undefined);
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });

  await client.connect(transport);
  const reference = await createPromptReference(root, {
    prompt: "delete private test record",
    sessionId: "approval-session",
    turnId: "approval-turn",
    riskTags: ["destructive"],
  });
  const pending = await client.callTool({
    name: "route_task",
    arguments: { prompt_ref: reference },
  });
  const pendingText = JSON.stringify(pending);
  const taskId = /task-[A-Za-z0-9_-]+/.exec(pendingText)?.[0];
  const approvalToken = /approval-[A-Za-z0-9_-]+/.exec(pendingText)?.[0];
  assert.ok(taskId);
  assert.ok(approvalToken);
  assert.match(pendingText, /awaiting approval/);

  const approved = await client.callTool({
    name: "approve_task",
    arguments: { task_id: taskId, approval_token: approvalToken },
  });
  const approvedText = JSON.stringify(approved);
  assert.equal(approved.isError, undefined);
  assert.match(approvedText, /Route: S/);
  assert.equal(approvedText.includes("delete private test record"), false);
});
