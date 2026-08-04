import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { resumeApprovedTask, runWorkflow, type TurnRunner } from "../../src/workflow/coordinator.js";
import {
  approvePendingTask,
  countPendingTasks,
  createPendingTask,
  rejectPendingTask,
  submitRouteFeedback,
} from "../../src/storage/pending-tasks.js";
import type { PromptEnvelope } from "../../src/storage/prompt-spool.js";
import type { AppServerTurnResult, RoleTarget } from "../../src/app-server/supervisor.js";

function envelope(overrides: Partial<PromptEnvelope> = {}): PromptEnvelope {
  return {
    version: 1,
    createdAt: new Date(0).toISOString(),
    expiresAt: new Date(Date.now() + 60_000).toISOString(),
    sessionKey: "session-key",
    turnKey: "turn-key",
    prompt: "delete this sensitive token=secret-value",
    cwd: "/repo/example",
    riskTags: ["destructive"],
    ...overrides,
  };
}

class ApprovalRunner implements TurnRunner {
  calls: RoleTarget[] = [];

  async runTurn(_prompt: string, target: RoleTarget): Promise<AppServerTurnResult> {
    this.calls.push(target);
    let text = "completed";
    if (target.role === "classifier") {
      text = JSON.stringify({
        route: "L",
        confidence: 1,
        risk_tags: [],
        ambiguity: 0,
        scope: 0,
        cross_module: 0,
        unknown_context: 0,
        reason_codes: ["test"],
        user_summary: "approved test",
      });
    } else if (target.role === "planner") {
      text = JSON.stringify({
        goal: "approved goal",
        completion_definition: "done",
        declared_scope: ["repo"],
        assumptions: [],
        evidence: [],
        prohibited_actions: [],
        steps: ["execute"],
        verification: ["check"],
        acceptance_criteria: ["done"],
        risk_tags: ["destructive"],
        approval_points: ["before delete"],
        major_deviation_rules: [],
      });
    } else if (target.role === "reviewer") {
      text = JSON.stringify({
        status: "pass",
        major_deviation: false,
        issues: [],
        summary: "approved",
      });
    }
    return {
      model: target.model,
      effort: target.effort,
      threadId: "thread",
      turnId: "turn",
      status: "completed",
      text,
    };
  }
}

async function tempRoot(t: { after(callback: () => void | Promise<void>): void }): Promise<string> {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-pending-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });
  return root;
}

test("high-risk route persists pending task and approval resumes bounded workflow", async (t) => {
  const root = await tempRoot(t);
  const runner = new ApprovalRunner();
  const pending = await runWorkflow(envelope(), runner, undefined, { dataDir: root });
  assert.equal(pending.status, "awaiting_approval");
  assert.equal(runner.calls.length, 0);
  assert.match(pending.taskId ?? "", /^task-/);
  assert.match(pending.approvalToken ?? "", /^approval-/);

  const completed = await resumeApprovedTask(
    root,
    pending.taskId as string,
    pending.approvalToken as string,
    runner,
  );
  assert.equal(completed.status, "succeeded");
  assert.deepEqual(
    runner.calls.map((target) => `${target.role}/${target.model}/${target.effort}`),
    [
      "classifier/auto/low",
      "planner/sol/xhigh",
      "executor/auto/max",
      "reviewer/sol/xhigh",
    ],
  );
  await assert.rejects(
    () => approvePendingTask(root, pending.taskId as string, pending.approvalToken as string),
    /not awaiting approval|already consumed/,
  );
});

test("rejection performs no executor call and pending files stay private", async (t) => {
  const root = await tempRoot(t);
  const pending = await createPendingTask(root, envelope(), ["destructive"]);
  const recordPath = path.join(root, "pending", `${pending.taskId}.json`);
  assert.equal((await stat(recordPath)).mode & 0o777, 0o600);
  const stored = await readFile(recordPath, "utf8");
  assert.equal(stored.includes("secret-value"), false);
  const rejected = await rejectPendingTask(root, pending.taskId);
  assert.equal(rejected.state, "rejected");
  assert.equal(await countPendingTasks(root), 0);
  assert.deepEqual(await readdir(path.join(root, "pending")), [`${pending.taskId}.json`]);
});

test("route feedback is weak until explicit confirmation", async (t) => {
  const root = await tempRoot(t);
  const weak = await submitRouteFeedback(root, {
    taskId: "task-feedback-1",
    label: "incorrect",
    comment: "natural language feedback",
  });
  assert.equal(weak.strength, "weak");
  assert.equal("comment" in weak, false);
  const strong = await submitRouteFeedback(root, {
    taskId: "task-feedback-1",
    label: "incorrect",
    confirmation: true,
    comment: "confirmed natural language feedback",
  });
  assert.equal(strong.strength, "strong");
  assert.equal(strong.comment, "confirmed natural language feedback");
});

test("concurrent approval consumes token once", async (t) => {
  const root = await tempRoot(t);
  const pending = await createPendingTask(root, envelope(), ["destructive"]);
  const outcomes = await Promise.allSettled([
    approvePendingTask(root, pending.taskId, pending.approvalToken),
    approvePendingTask(root, pending.taskId, pending.approvalToken),
  ]);
  assert.equal(outcomes.filter((item) => item.status === "fulfilled").length, 1);
  assert.equal(outcomes.filter((item) => item.status === "rejected").length, 1);
});
