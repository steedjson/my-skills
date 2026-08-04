import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { runMaintenance } from "../../src/maintenance.js";

test("maintenance is weekly-idempotent and never auto-activates a candidate", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "semantic-router-maintenance-"));
  t.after(async () => {
    const { rm } = await import("node:fs/promises");
    await rm(root, { recursive: true, force: true });
  });

  const first = await runMaintenance(root, { now: 1_000, force: true });
  assert.equal(first.status, "completed");
  assert.equal(first.candidateId, undefined);
  assert.match(first.reason ?? "", /strong feedback/);

  const skipped = await runMaintenance(root, { now: 2_000 });
  assert.equal(skipped.status, "skipped");
  assert.equal(skipped.runId, first.runId);

  const later = await runMaintenance(root, { now: 1_000 + 7 * 24 * 60 * 60 * 1000 + 1 });
  assert.equal(later.status, "completed");
  assert.notEqual(later.runId, first.runId);
});
