import { readdirSync } from "node:fs";
import os from "node:os";
import path from "node:path";

export const PLUGIN_NAME = "semantic-model-router";
export const PLUGIN_VERSION = "0.1.0";
export const CONTROL_PLANE_PHASE = "phase-6-maintenance";
export const PROMPT_TTL_MS = 10 * 60 * 1000;

export class RouterConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RouterConfigError";
  }
}

export function routerDataDir(
  env: NodeJS.ProcessEnv = process.env,
  cwd = process.cwd(),
): string {
  const configured =
    env.SEMANTIC_ROUTER_DATA_DIR ?? env.PLUGIN_DATA ?? env.CLAUDE_PLUGIN_DATA;
  if (configured?.trim()) return path.resolve(configured);

  const codexHome = path.resolve(env.CODEX_HOME ?? path.join(os.homedir(), ".codex"));
  const marketplace = marketplaceFromPluginCache(cwd);
  if (marketplace) {
    return path.join(codexHome, "plugins", "data", `${PLUGIN_NAME}-${marketplace}`);
  }

  const dataRoot = path.join(codexHome, "plugins", "data");
  try {
    const candidates = readdirSync(dataRoot, { withFileTypes: true }).filter(
      (entry) =>
        entry.isDirectory() && entry.name.startsWith(`${PLUGIN_NAME}-`),
    );
    if (candidates.length === 1 && candidates[0]) {
      return path.join(dataRoot, candidates[0].name);
    }
  } catch {
    // No installed plugin data directory is available.
  }
  throw new RouterConfigError("Router data directory is unavailable");
}

function marketplaceFromPluginCache(cwd: string): string | undefined {
  const parts = path.resolve(cwd).split(path.sep);
  for (let index = 0; index < parts.length - 3; index += 1) {
    if (parts[index] !== "plugins" || parts[index + 1] !== "cache") continue;
    const marketplace = parts[index + 2];
    const plugin = parts[index + 3];
    if (
      plugin === PLUGIN_NAME &&
      marketplace &&
      /^[A-Za-z0-9._-]+$/.test(marketplace)
    ) {
      return marketplace;
    }
  }
  return undefined;
}
