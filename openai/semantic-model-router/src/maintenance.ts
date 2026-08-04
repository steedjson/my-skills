import { randomUUID } from "node:crypto";
import {
  chmod,
  lstat,
  mkdir,
  readFile,
  rename,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

import { routerDataDir } from "./config.js";
import {
  cleanupPolicyData,
  createPolicyCandidate,
  PolicyStoreError,
  type PolicyCandidateRecord,
} from "./learning/policy-store.js";
import { redactText } from "./security/redaction.js";

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

export interface MaintenanceResult {
  runId: string;
  status: "completed" | "skipped";
  reason?: string;
  removedRecords: number;
  candidateId?: string;
  candidateState?: PolicyCandidateRecord["state"];
}

interface MaintenanceState {
  version: 1;
  lastRunAt: string;
  runId: string;
}

function maintenanceDir(dataDir: string): string {
  return path.join(dataDir, "maintenance");
}

function statePath(dataDir: string): string {
  return path.join(maintenanceDir(dataDir), "state.json");
}

function resultPath(dataDir: string, runId: string): string {
  return path.join(maintenanceDir(dataDir), `${runId}.json`);
}

async function readState(dataDir: string): Promise<MaintenanceState | undefined> {
  try {
    const stats = await lstat(statePath(dataDir));
    if (!stats.isFile() || stats.isSymbolicLink()) return undefined;
    const value = JSON.parse(await readFile(statePath(dataDir), "utf8")) as Record<string, unknown>;
    if (value.version !== 1 || typeof value.lastRunAt !== "string" || typeof value.runId !== "string") return undefined;
    return value as unknown as MaintenanceState;
  } catch {
    return undefined;
  }
}

async function writePrivateJson(filePath: string, value: unknown): Promise<void> {
  await mkdir(path.dirname(filePath), { recursive: true, mode: 0o700 });
  await chmod(path.dirname(filePath), 0o700);
  const temporary = `${filePath}.${process.pid}.${randomUUID()}.tmp`;
  await writeFile(temporary, JSON.stringify(value), { encoding: "utf8", mode: 0o600 });
  await chmod(temporary, 0o600);
  await rename(temporary, filePath);
  await chmod(filePath, 0o600);
}

export async function runMaintenance(
  dataDir: string,
  options: { now?: number; force?: boolean } = {},
): Promise<MaintenanceResult> {
  const now = options.now ?? Date.now();
  const previous = await readState(dataDir);
  if (!options.force && previous && Date.parse(previous.lastRunAt) + WEEK_MS > now) {
    return {
      runId: previous.runId,
      status: "skipped",
      reason: "weekly maintenance window has not elapsed",
      removedRecords: 0,
    };
  }

  const runId = `maintenance-${randomUUID()}`;
  const removedRecords = await cleanupPolicyData(dataDir, now);
  const result: MaintenanceResult = {
    runId,
    status: "completed",
    removedRecords,
  };
  try {
    const candidate = await createPolicyCandidate(dataDir, now);
    result.candidateId = candidate.candidateId;
    result.candidateState = candidate.state;
  } catch (error) {
    if (error instanceof PolicyStoreError) {
      result.reason = redactText(error.message).replace(/[\r\n]+/g, " ").slice(0, 240);
    } else {
      result.reason = "candidate generation unavailable";
    }
  }
  await writePrivateJson(statePath(dataDir), {
    version: 1,
    lastRunAt: new Date(now).toISOString(),
    runId,
  });
  await writePrivateJson(resultPath(dataDir, runId), result);
  return result;
}

async function main(): Promise<void> {
  const dataDir = routerDataDir();
  const force = process.env.SEMANTIC_ROUTER_MAINTENANCE_FORCE === "1";
  const result = await runMaintenance(dataDir, { force });
  const fields = [
    `maintenance: ${result.status}`,
    `run_id: ${result.runId}`,
    `removed_records: ${result.removedRecords}`,
    ...(result.candidateId ? [`candidate_id: ${result.candidateId}`, `candidate_state: ${result.candidateState}`] : []),
    ...(result.reason ? [`reason: ${result.reason}`] : []),
  ];
  process.stdout.write(`${fields.join("\n")}\n`);
}

if (process.argv[1]?.endsWith("maintenance.js")) {
  main().catch((error) => {
    process.stderr.write(`${redactText(error instanceof Error ? error.message : String(error))}\n`);
    process.exitCode = 1;
  });
}
