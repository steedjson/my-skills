import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { routerDataDir } from "../../src/config.js";

test("explicit plugin data directory wins", () => {
  assert.equal(
    routerDataDir({ PLUGIN_DATA: "/private/plugin-data" }, "/workspace"),
    path.resolve("/private/plugin-data"),
  );
});

test("MCP derives plugin data directory from installed cache path", () => {
  const codexHome = path.resolve("/private/codex-home");
  const cwd = path.join(
    codexHome,
    "plugins",
    "cache",
    "my-skills-local",
    "semantic-model-router",
    "0.1.0",
  );
  assert.equal(
    routerDataDir({ CODEX_HOME: codexHome }, cwd),
    path.join(
      codexHome,
      "plugins",
      "data",
      "semantic-model-router-my-skills-local",
    ),
  );
});
