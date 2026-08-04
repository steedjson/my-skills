import { createHash } from "node:crypto";
import { chmod, mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";

function stateKey(sessionId: string): string {
  return createHash("sha256").update(sessionId).digest("hex").slice(0, 32);
}

function statePath(dataDir: string, sessionId: string): string {
  return path.join(dataDir, "sessions", `${stateKey(sessionId)}.json`);
}

export async function isAutoRoutingEnabled(
  dataDir: string,
  sessionId: string,
): Promise<boolean> {
  try {
    const value = JSON.parse(await readFile(statePath(dataDir, sessionId), "utf8"));
    return value.enabled !== false;
  } catch {
    return true;
  }
}

export async function setAutoRouting(
  dataDir: string,
  sessionId: string,
  enabled: boolean,
): Promise<void> {
  const directory = path.join(dataDir, "sessions");
  await mkdir(directory, { recursive: true, mode: 0o700 });
  await chmod(directory, 0o700);
  const target = statePath(dataDir, sessionId);
  const temporary = `${target}.${process.pid}.tmp`;
  await writeFile(
    temporary,
    JSON.stringify({ enabled, updatedAt: new Date().toISOString() }),
    { encoding: "utf8", mode: 0o600 },
  );
  await chmod(temporary, 0o600);
  await rename(temporary, target);
}
