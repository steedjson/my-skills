import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  BASELINE_POLICY,
  activatePolicyCandidate,
  cleanupPolicyData,
  createPolicyCandidate,
  createPolicyCandidateFromSpec,
  evaluatePolicy,
  getActivePolicy,
  readPolicyCandidate,
  rollbackPolicy,
} from "../../src/learning/policy-store.js";
import { submitRouteFeedback } from "../../src/storage/pending-tasks.js";

async function tempRoot(t: { after(callback: () => void | Promise<void>): void }): Promise<string> {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-policy-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });
  return root;
}

test("frozen replay rejects worse policy and accepts safe lower-S policy", () => {
  const worse = evaluatePolicy({
    versionId: "worse",
    confidenceThreshold: 0.9,
    ambiguousToS: true,
  });
  assert.equal(worse.accepted, false);
  assert.ok(worse.reasons.length > 0);

  const better = evaluatePolicy({
    versionId: "better",
    confidenceThreshold: 0.55,
    ambiguousToS: true,
  });
  assert.equal(better.accepted, true);
  assert.equal(better.candidate.missedHighRisk, 0);
  assert.ok(better.candidate.solCalls < better.baseline.solCalls);
});

test("candidate lifecycle activates and rolls back without source changes", async (t) => {
  const root = await tempRoot(t);
  const candidate = await createPolicyCandidateFromSpec(
    root,
    { versionId: "safe-candidate", confidenceThreshold: 0.55, ambiguousToS: true },
    10,
  );
  assert.equal(candidate.state, "pending");
  const reviewed = await readPolicyCandidate(root, candidate.candidateId);
  assert.equal(reviewed.evaluation.accepted, true);

  const active = await activatePolicyCandidate(root, candidate.candidateId, "ACTIVATE_POLICY");
  assert.equal(active.candidateId, candidate.candidateId);
  assert.equal((await getActivePolicy(root)).versionId, candidate.candidateId);

  const rolledBack = await rollbackPolicy(root, candidate.candidateId, "ROLLBACK_POLICY");
  assert.equal(rolledBack.spec.versionId, BASELINE_POLICY.versionId);
  assert.equal((await getActivePolicy(root)).versionId, BASELINE_POLICY.versionId);
});

test("candidate generation requires strong feedback and never stores prompt text", async (t) => {
  const root = await tempRoot(t);
  for (let index = 0; index < 10; index += 1) {
    await submitRouteFeedback(root, {
      taskId: `task-feedback-${index.toString().padStart(2, "0")}`,
      label: "incorrect",
      confirmation: true,
      comment: "confirmed route feedback",
    });
  }
  const candidate = await createPolicyCandidate(root);
  assert.equal(candidate.strongFeedbackCount, 10);
  assert.equal(candidate.spec.confidenceThreshold, 0.55);
  assert.equal(JSON.stringify(candidate).includes("confirmed route feedback"), false);
});

test("retention removes expired weak feedback but keeps strong feedback", async (t) => {
  const root = await tempRoot(t);
  const old = Date.now() - 91 * 24 * 60 * 60 * 1000;
  await submitRouteFeedback(root, {
    taskId: "task-weak-retention",
    label: "correct",
  }, old);
  await submitRouteFeedback(root, {
    taskId: "task-strong-retention",
    label: "correct",
    confirmation: true,
  }, old);
  assert.equal(await cleanupPolicyData(root), 1);
});
