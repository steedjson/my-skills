import assert from "node:assert/strict";
import test from "node:test";

import { parseClassifierResult } from "../../src/routing/classifier.js";
import { decideRoute } from "../../src/routing/policy.js";
import { runWorkflow, type TurnRunner } from "../../src/workflow/coordinator.js";
import type {
  AppServerTurnResult,
  RoleTarget,
} from "../../src/app-server/supervisor.js";
import type { PromptEnvelope } from "../../src/storage/prompt-spool.js";

function envelope(overrides: Partial<PromptEnvelope> = {}): PromptEnvelope {
  return {
    version: 1,
    createdAt: new Date(0).toISOString(),
    expiresAt: new Date(Date.now() + 60_000).toISOString(),
    sessionKey: "session",
    turnKey: "turn",
    prompt: "implement requested change",
    riskTags: [],
    ...overrides,
  };
}

function classifier(route: "L" | "S"): string {
  return JSON.stringify({
    route,
    confidence: 0.94,
    risk_tags: [],
    ambiguity: 0.1,
    scope: 0.4,
    cross_module: route === "S" ? 0.8 : 0.1,
    unknown_context: 0.1,
    reason_codes: [route === "S" ? "cross-module" : "explicit-scope"],
    user_summary: route === "S" ? "cross-module reasoning" : "single scoped change",
  });
}

function packet(): string {
  return JSON.stringify({
    goal: "implement requested change",
    completion_definition: "tests pass and acceptance criteria hold",
    declared_scope: ["src"],
    assumptions: ["repository state is current"],
    evidence: ["user request"],
    prohibited_actions: ["no destructive side effects"],
    steps: ["inspect", "implement", "verify"],
    verification: ["npm test"],
    acceptance_criteria: ["requested behavior works"],
    risk_tags: [],
    approval_points: [],
    major_deviation_rules: ["stop on scope expansion"],
  });
}

function review(status: "pass" | "repair", majorDeviation = false): string {
  return JSON.stringify({
    status,
    major_deviation: majorDeviation,
    issues: status === "pass" ? [] : ["verification still failing"],
    summary: status === "pass" ? "acceptance criteria verified" : "repair verification failure",
  });
}

class FakeRunner implements TurnRunner {
  calls: Array<{ prompt: string; target: RoleTarget }> = [];
  reviewerResults: string[] = [];
  classifierText = classifier("L");

  async runTurn(prompt: string, target: RoleTarget): Promise<AppServerTurnResult> {
    this.calls.push({ prompt, target });
    let text = "implementation complete";
    if (target.role === "classifier") text = this.classifierText;
    else if (target.role === "planner") text = packet();
    else if (target.role === "reviewer") text = this.reviewerResults.shift() ?? review("pass");
    return {
      model: target.model,
      effort: target.effort,
      threadId: `thread-${this.calls.length}`,
      turnId: `turn-${this.calls.length}`,
      status: "completed",
      text,
    };
  }
}

test("classifier parser accepts fenced JSON and policy forces hard risk to approval", () => {
  const parsed = parseClassifierResult(`\n\`\`\`json\n${classifier("L")}\n\`\`\``);
  assert.equal(parsed?.route, "L");
  const decision = decideRoute({
    override: "L",
    hardRiskTags: ["permission_or_security"],
    classifier: parsed,
  });
  assert.equal(decision.route, "S");
  assert.equal(decision.requiresApproval, true);
});

test("L route uses auto classifier then auto executor", async () => {
  const runner = new FakeRunner();
  const result = await runWorkflow(envelope(), runner);
  assert.equal(result.route, "L");
  assert.equal(result.status, "succeeded");
  assert.deepEqual(
    runner.calls.map(({ target }) => `${target.role}/${target.model}/${target.effort}`),
    ["classifier/auto/low", "executor/auto/max"],
  );
  assert.match(result.receipt, /classifier=auto\/low -> executor=auto\/max/);
});

test("S route runs planner, executor, and independent reviewer", async () => {
  const runner = new FakeRunner();
  runner.classifierText = classifier("S");
  runner.reviewerResults = [review("pass")];
  const result = await runWorkflow(envelope(), runner);
  assert.equal(result.route, "S");
  assert.equal(result.status, "succeeded");
  assert.deepEqual(
    runner.calls.map(({ target }) => `${target.role}/${target.model}/${target.effort}`),
    [
      "classifier/auto/low",
      "planner/auto/xhigh",
      "executor/auto/max",
      "reviewer/auto/xhigh",
    ],
  );
  assert.match(result.receipt, /planner=auto\/xhigh -> executor=auto\/max -> reviewer=auto\/xhigh/);
});

test("major deviation replans, while repair loop stays within call limits", async () => {
  const runner = new FakeRunner();
  runner.classifierText = classifier("S");
  runner.reviewerResults = [review("repair", true), review("pass")];
  const result = await runWorkflow(envelope(), runner);
  assert.equal(result.status, "succeeded");
  assert.equal(runner.calls.filter(({ target }) => target.role === "planner" || target.role === "reviewer").length, 4);
  assert.equal(runner.calls.filter(({ target }) => target.role === "executor").length, 2);
});

test("third repair request blocks instead of looping", async () => {
  const runner = new FakeRunner();
  runner.classifierText = classifier("S");
  runner.reviewerResults = [review("repair"), review("repair"), review("repair")];
  const result = await runWorkflow(envelope(), runner);
  assert.equal(result.status, "blocked");
  assert.equal(runner.calls.filter(({ target }) => target.role === "executor").length, 3);
  assert.equal(runner.calls.filter(({ target }) => target.role === "planner" || target.role === "reviewer").length, 4);
});

test("@sol and @luna force model family while retaining route semantics", async () => {
  const solRunner = new FakeRunner();
  solRunner.classifierText = classifier("L");
  const solResult = await runWorkflow(envelope({ override: "S" }), solRunner);
  assert.equal(solResult.route, "S");
  assert.ok(solRunner.calls.every(({ target }) => target.model === "sol"));

  const lunaRunner = new FakeRunner();
  const lunaResult = await runWorkflow(envelope({ override: "L" }), lunaRunner);
  assert.equal(lunaResult.route, "L");
  assert.ok(lunaRunner.calls.every(({ target }) => target.model === "luna"));
});

test("hard risk pauses before classifier and executor even with Luna override", async () => {
  const runner = new FakeRunner();
  const result = await runWorkflow(
    envelope({ override: "L", riskTags: ["destructive"] }),
    runner,
  );
  assert.equal(result.status, "awaiting_approval");
  assert.equal(runner.calls.length, 0);
});
