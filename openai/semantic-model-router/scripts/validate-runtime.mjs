import { access, readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const required = [
  ".codex-plugin/plugin.json",
  ".mcp.json",
  "hooks/hooks.json",
  "hooks/user-prompt-submit.mjs",
  "dist/server.js",
  "dist/maintenance.js",
  "scripts/install-launchd.mjs",
];

for (const relative of required) {
  await access(path.join(root, relative));
}

const mcp = JSON.parse(await readFile(path.join(root, ".mcp.json"), "utf8"));
const server = mcp.mcpServers?.["semantic-model-router"];
if (server?.command !== "node" || server?.args?.[0] !== "dist/server.js") {
  throw new Error("semantic-model-router MCP entry does not target dist/server.js");
}

const hooks = JSON.parse(await readFile(path.join(root, "hooks/hooks.json"), "utf8"));
const command = hooks.hooks?.UserPromptSubmit?.[0]?.hooks?.[0]?.command;
if (!command?.includes("${PLUGIN_ROOT}/hooks/user-prompt-submit.mjs")) {
  throw new Error("UserPromptSubmit hook does not use PLUGIN_ROOT");
}

process.stdout.write("runtime paths valid\n");
