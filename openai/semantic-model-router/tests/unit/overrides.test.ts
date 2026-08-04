import assert from "node:assert/strict";
import test from "node:test";

import { detectRiskTags } from "../../src/routing/hard-rules.js";
import { parseControlCommand } from "../../src/routing/overrides.js";

test("route overrides only match leading control commands", () => {
  assert.deepEqual(parseControlCommand("@sol analyze this"), {
    kind: "route",
    route: "S",
  });
  assert.deepEqual(parseControlCommand("  @luna implement plan"), {
    kind: "route",
    route: "L",
  });
  assert.deepEqual(parseControlCommand("mention @sol in docs"), { kind: "none" });
});

test("bypass, session, approval, and feedback commands parse", () => {
  assert.deepEqual(parseControlCommand("@current keep model"), { kind: "current" });
  assert.deepEqual(parseControlCommand("@auto-off"), {
    kind: "auto",
    enabled: false,
  });
  assert.deepEqual(parseControlCommand("@auto-on"), {
    kind: "auto",
    enabled: true,
  });
  assert.deepEqual(parseControlCommand("@approve task_42"), {
    kind: "approval",
    action: "approve",
    taskId: "task_42",
  });
  assert.deepEqual(parseControlCommand("@route-bad task_42"), {
    kind: "feedback",
    label: "incorrect",
    taskId: "task_42",
  });
});

test("hard-risk rules cover Chinese destructive and permission work", () => {
  assert.deepEqual(
    detectRiskTags("删除租户数据并修改权限，完成后部署"),
    ["destructive", "external_side_effect", "permission_or_security"],
  );
});
