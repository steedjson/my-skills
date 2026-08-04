import { createHash, randomUUID } from "node:crypto";
import {
  chmod,
  lstat,
  mkdir,
  readFile,
  readdir,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

import { redactText } from "../security/redaction.js";

const CANDIDATE_ID_PATTERN = /^policy-candidate-[A-Za-z0-9_-]{8,128}$/;
const VERSION_ID_PATTERN = /^[A-Za-z0-9_.-]{1,128}$/;
const WEAK_FEEDBACK_TTL_MS = 90 * 24 * 60 * 60 * 1000;

export interface PolicySpec {
  versionId: string;
  confidenceThreshold: number;
  ambiguousToS: boolean;
}

export interface ReplayMetrics {
  totalCases: number;
  weightedAccuracy: number;
  sRouteRecall: number;
  missedHighRisk: number;
  solCalls: number;
}

export interface PolicyEvaluation {
  accepted: boolean;
  reasons: string[];
  baseline: ReplayMetrics;
  candidate: ReplayMetrics;
}

export type PolicyCandidateState = "pending" | "rejected" | "active" | "rolled_back";

export interface PolicyCandidateRecord {
  version: 1;
  candidateId: string;
  state: PolicyCandidateState;
  createdAt: string;
  expiresAt: string;
  source: "deterministic-feedback" | "manual-replay";
  strongFeedbackCount: number;
  spec: PolicySpec;
  evaluation: PolicyEvaluation;
}

export interface ActivePolicyRecord {
  version: 1;
  spec: PolicySpec;
  activatedAt: string;
  candidateId?: string;
}

interface PolicyHistoryRecord {
  version: 1;
  spec: PolicySpec;
  savedAt: string;
  candidateId?: string;
}

export class PolicyStoreError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PolicyStoreError";
  }
}

export const BASELINE_POLICY: PolicySpec = {
  versionId: "baseline",
  confidenceThreshold: 0.65,
  ambiguousToS: true,
};

function policyDir(dataDir: string): string {
  return path.join(dataDir, "policies");
}

function candidatesDir(dataDir: string): string {
  return path.join(policyDir(dataDir), "candidates");
}

function historyDir(dataDir: string): string {
  return path.join(policyDir(dataDir), "history");
}

function activePath(dataDir: string): string {
  return path.join(policyDir(dataDir), "active.json");
}

function candidatePath(dataDir: string, candidateId: string): string {
  if (!CANDIDATE_ID_PATTERN.test(candidateId)) throw new PolicyStoreError("Policy candidate id is invalid");
  return path.join(candidatesDir(dataDir), `${candidateId}.json`);
}

function hash(value: string): string {
  return createHash("sha256").update(value).digest("hex").slice(0, 16);
}

async function ensurePrivateDirectory(directory: string): Promise<void> {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  await chmod(directory, 0o700);
}

async function writePrivateJson(filePath: string, value: unknown): Promise<void> {
  await ensurePrivateDirectory(path.dirname(filePath));
  const temporary = `${filePath}.${process.pid}.${randomUUID()}.tmp`;
  await writeFile(temporary, JSON.stringify(value), { encoding: "utf8", mode: 0o600 });
  await chmod(temporary, 0o600);
  await rename(temporary, filePath);
  await chmod(filePath, 0o600);
}

async function readJson(filePath: string): Promise<unknown> {
  try {
    const stats = await lstat(filePath);
    if (!stats.isFile() || stats.isSymbolicLink()) throw new PolicyStoreError("Policy record is not a private file");
    return JSON.parse(await readFile(filePath, "utf8")) as unknown;
  } catch (error) {
    if (error instanceof PolicyStoreError) throw error;
    throw new PolicyStoreError("Policy record is missing or invalid");
  }
}

export function validatePolicySpec(spec: PolicySpec): PolicySpec {
  if (!VERSION_ID_PATTERN.test(spec.versionId)) throw new PolicyStoreError("Policy version id is invalid");
  if (!Number.isFinite(spec.confidenceThreshold) || spec.confidenceThreshold < 0.4 || spec.confidenceThreshold > 0.9) {
    throw new PolicyStoreError("Policy confidence threshold is outside safe bounds");
  }
  if (typeof spec.ambiguousToS !== "boolean") throw new PolicyStoreError("Policy ambiguity rule is invalid");
  return {
    versionId: redactText(spec.versionId).slice(0, 128),
    confidenceThreshold: Number(spec.confidenceThreshold.toFixed(4)),
    ambiguousToS: spec.ambiguousToS,
  };
}

export async function getActivePolicy(dataDir: string): Promise<PolicySpec> {
  try {
    const value = await readJson(activePath(dataDir));
    if (!isActivePolicyRecord(value)) return BASELINE_POLICY;
    return validatePolicySpec(value.spec);
  } catch {
    return BASELINE_POLICY;
  }
}

export async function getActivePolicyRecord(dataDir: string): Promise<ActivePolicyRecord> {
  try {
    const value = await readJson(activePath(dataDir));
    if (isActivePolicyRecord(value)) return value;
  } catch {
    // No active policy yet.
  }
  return { version: 1, spec: BASELINE_POLICY, activatedAt: new Date(0).toISOString() };
}

export function evaluatePolicy(specInput: PolicySpec): PolicyEvaluation {
  const spec = validatePolicySpec(specInput);
  const baseline = evaluateReplay(BASELINE_POLICY);
  const candidate = evaluateReplay(spec);
  const reasons: string[] = [];
  if (candidate.missedHighRisk !== 0) reasons.push("missed high-risk case");
  if (candidate.sRouteRecall < 0.95) reasons.push("S-route recall below 95 percent");
  if (candidate.weightedAccuracy < baseline.weightedAccuracy) reasons.push("weighted accuracy below baseline");
  if (
    candidate.weightedAccuracy === baseline.weightedAccuracy &&
    candidate.solCalls > baseline.solCalls * 0.9
  ) {
    reasons.push("equal accuracy does not reduce Sol calls by 10 percent");
  }
  return { accepted: reasons.length === 0, reasons, baseline, candidate };
}

export async function createPolicyCandidate(
  dataDir: string,
  now = Date.now(),
): Promise<PolicyCandidateRecord> {
  const feedback = await readStrongFeedback(dataDir);
  if (feedback.count < 10) {
    throw new PolicyStoreError("At least 10 strong feedback labels are required");
  }
  const threshold = feedback.incorrect > 0 ? 0.55 : BASELINE_POLICY.confidenceThreshold;
  return createPolicyCandidateFromSpec(
    dataDir,
    {
      versionId: `candidate-${hash(`${now}\0${feedback.count}\0${feedback.incorrect}`)}`,
      confidenceThreshold: threshold,
      ambiguousToS: true,
    },
    feedback.count,
    "deterministic-feedback",
    now,
  );
}

export async function createPolicyCandidateFromSpec(
  dataDir: string,
  specInput: PolicySpec,
  strongFeedbackCount = 0,
  source: PolicyCandidateRecord["source"] = "manual-replay",
  now = Date.now(),
): Promise<PolicyCandidateRecord> {
  const spec = validatePolicySpec(specInput);
  const evaluation = evaluatePolicy(spec);
  const candidateId = `policy-candidate-${randomUUID()}`;
  const record: PolicyCandidateRecord = {
    version: 1,
    candidateId,
    state: evaluation.accepted ? "pending" : "rejected",
    createdAt: new Date(now).toISOString(),
    expiresAt: new Date(now + WEAK_FEEDBACK_TTL_MS).toISOString(),
    source,
    strongFeedbackCount,
    spec: { ...spec, versionId: candidateId },
    evaluation,
  };
  await writePrivateJson(candidatePath(dataDir, candidateId), record);
  return record;
}

export async function readPolicyCandidate(
  dataDir: string,
  candidateId: string,
): Promise<PolicyCandidateRecord> {
  const value = await readJson(candidatePath(dataDir, candidateId));
  if (!isPolicyCandidateRecord(value)) throw new PolicyStoreError("Policy candidate record is invalid");
  return value;
}

export async function activatePolicyCandidate(
  dataDir: string,
  candidateId: string,
  confirmation: string,
  now = Date.now(),
): Promise<ActivePolicyRecord> {
  if (confirmation !== "ACTIVATE_POLICY") throw new PolicyStoreError("Explicit policy activation confirmation required");
  const candidate = await readPolicyCandidate(dataDir, candidateId);
  if (candidate.state !== "pending" || !candidate.evaluation.accepted) {
    throw new PolicyStoreError("Policy candidate is not eligible for activation");
  }
  const active = await getActivePolicyRecord(dataDir);
  const history: PolicyHistoryRecord = {
    version: 1,
    spec: active.spec,
    savedAt: new Date(now).toISOString(),
    ...(active.candidateId ? { candidateId: active.candidateId } : {}),
  };
  await writePrivateJson(path.join(historyDir(dataDir), `${candidateId}-${now}.json`), history);
  const next: ActivePolicyRecord = {
    version: 1,
    spec: candidate.spec,
    activatedAt: new Date(now).toISOString(),
    candidateId,
  };
  await writePrivateJson(activePath(dataDir), next);
  await writePrivateJson(candidatePath(dataDir, candidateId), { ...candidate, state: "active" });
  return next;
}

export async function rollbackPolicy(
  dataDir: string,
  versionId: string,
  confirmation: string,
  now = Date.now(),
): Promise<ActivePolicyRecord> {
  if (confirmation !== "ROLLBACK_POLICY") throw new PolicyStoreError("Explicit policy rollback confirmation required");
  const active = await getActivePolicyRecord(dataDir);
  if (active.spec.versionId !== versionId && active.candidateId !== versionId) {
    throw new PolicyStoreError("Requested policy version is not active");
  }
  const previous = await latestHistory(dataDir);
  if (!previous) throw new PolicyStoreError("No previous policy version is available");
  const next: ActivePolicyRecord = {
    version: 1,
    spec: previous.spec,
    activatedAt: new Date(now).toISOString(),
    ...(previous.candidateId ? { candidateId: previous.candidateId } : {}),
  };
  await writePrivateJson(activePath(dataDir), next);
  if (active.candidateId) {
    const candidate = await readPolicyCandidate(dataDir, active.candidateId);
    await writePrivateJson(candidatePath(dataDir, active.candidateId), { ...candidate, state: "rolled_back" });
  }
  return next;
}

export async function cleanupPolicyData(dataDir: string, now = Date.now()): Promise<number> {
  let removed = 0;
  try {
    const names = await readdir(candidatesDir(dataDir));
    for (const name of names) {
      if (!name.endsWith(".json")) continue;
      const filePath = path.join(candidatesDir(dataDir), name);
      try {
        const value = await readJson(filePath);
        if (isPolicyCandidateRecord(value) && Date.parse(value.expiresAt) <= now && value.state !== "active") {
          await rm(filePath, { force: true });
          removed += 1;
        }
      } catch {
        // Ignore malformed candidate records.
      }
    }
  } catch {
    // Directory may not exist yet.
  }
  try {
    const names = await readdir(path.join(dataDir, "feedback"));
    for (const name of names) {
      if (!name.endsWith(".json")) continue;
      const filePath = path.join(dataDir, "feedback", name);
      try {
        const value = await readJson(filePath);
        if (!value || typeof value !== "object") continue;
        const item = value as Record<string, unknown>;
        if (
          item.strength === "weak" &&
          typeof item.createdAt === "string" &&
          Date.parse(item.createdAt) + WEAK_FEEDBACK_TTL_MS <= now
        ) {
          await rm(filePath, { force: true });
          removed += 1;
        }
      } catch {
        // Ignore malformed feedback records.
      }
    }
  } catch {
    // Directory may not exist yet.
  }
  return removed;
}

export async function countPendingPolicyCandidates(dataDir: string): Promise<number> {
  try {
    const names = await readdir(candidatesDir(dataDir));
    let count = 0;
    for (const name of names) {
      if (!name.endsWith(".json")) continue;
      try {
        const value = await readJson(path.join(candidatesDir(dataDir), name));
        if (isPolicyCandidateRecord(value) && value.state === "pending") count += 1;
      } catch {
        // Ignore malformed candidate records.
      }
    }
    return count;
  } catch {
    return 0;
  }
}

async function readStrongFeedback(dataDir: string): Promise<{ count: number; incorrect: number }> {
  const directory = path.join(dataDir, "feedback");
  let names: string[];
  try {
    names = await readdir(directory);
  } catch {
    return { count: 0, incorrect: 0 };
  }
  let count = 0;
  let incorrect = 0;
  for (const name of names) {
    if (!name.endsWith(".json")) continue;
    try {
      const value = await readJson(path.join(directory, name));
      if (!value || typeof value !== "object") continue;
      const item = value as Record<string, unknown>;
      if (item.strength !== "strong") continue;
      count += 1;
      if (item.label === "incorrect") incorrect += 1;
    } catch {
      // Ignore malformed feedback records.
    }
  }
  return { count, incorrect };
}

async function latestHistory(dataDir: string): Promise<PolicyHistoryRecord | undefined> {
  let names: string[];
  try {
    names = (await readdir(historyDir(dataDir))).filter((name) => name.endsWith(".json")).sort().reverse();
  } catch {
    return undefined;
  }
  for (const name of names) {
    try {
      const value = await readJson(path.join(historyDir(dataDir), name));
      if (isPolicyHistoryRecord(value)) return value;
    } catch {
      // Ignore malformed history records.
    }
  }
  return undefined;
}

function evaluateReplay(spec: PolicySpec): ReplayMetrics {
  const cases = [
    { classifierRoute: "L", confidence: 0.95, highRisk: true, expectedRoute: "S", expectedApproval: true },
    { classifierRoute: "L", confidence: 0.95, highRisk: true, expectedRoute: "S", expectedApproval: true },
    { classifierRoute: "L", confidence: 0.95, highRisk: false, expectedRoute: "L", expectedApproval: false },
    { classifierRoute: "L", confidence: 0.95, highRisk: false, expectedRoute: "L", expectedApproval: false },
    { classifierRoute: "L", confidence: 0.95, highRisk: false, expectedRoute: "L", expectedApproval: false },
    { classifierRoute: "L", confidence: 0.95, highRisk: false, expectedRoute: "L", expectedApproval: false },
    { classifierRoute: "S", confidence: 0.95, highRisk: false, expectedRoute: "S", expectedApproval: false },
    { classifierRoute: "S", confidence: 0.95, highRisk: false, expectedRoute: "S", expectedApproval: false },
    { classifierRoute: "L", confidence: 0.6, highRisk: false, expectedRoute: "L", expectedApproval: false },
    { classifierRoute: "L", confidence: 0.6, highRisk: false, expectedRoute: "L", expectedApproval: false },
    { classifierRoute: "S", confidence: 0.6, highRisk: false, expectedRoute: "S", expectedApproval: false },
  ] as const;
  let correct = 0;
  let expectedS = 0;
  let recalledS = 0;
  let missedHighRisk = 0;
  let solCalls = 0;
  for (const item of cases) {
    const route = item.highRisk
      ? "S"
      : item.confidence < spec.confidenceThreshold && spec.ambiguousToS
        ? "S"
        : item.classifierRoute;
    const approval = item.highRisk;
    if (route === item.expectedRoute) correct += 1;
    if (item.expectedRoute === "S") {
      expectedS += 1;
      if (route === "S") recalledS += 1;
    }
    if (item.highRisk && (!approval || route !== "S")) missedHighRisk += 1;
    if (route === "S") solCalls += 1;
  }
  return {
    totalCases: cases.length,
    weightedAccuracy: correct / cases.length,
    sRouteRecall: expectedS ? recalledS / expectedS : 1,
    missedHighRisk,
    solCalls,
  };
}

function isActivePolicyRecord(value: unknown): value is ActivePolicyRecord {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return item.version === 1 && typeof item.activatedAt === "string" && isPolicySpec(item.spec);
}

function isPolicyHistoryRecord(value: unknown): value is PolicyHistoryRecord {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return item.version === 1 && typeof item.savedAt === "string" && isPolicySpec(item.spec);
}

function isPolicyCandidateRecord(value: unknown): value is PolicyCandidateRecord {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    item.version === 1 &&
    typeof item.candidateId === "string" && CANDIDATE_ID_PATTERN.test(item.candidateId) &&
    typeof item.state === "string" &&
    typeof item.createdAt === "string" &&
    typeof item.expiresAt === "string" &&
    typeof item.strongFeedbackCount === "number" &&
    isPolicySpec(item.spec) &&
    isPolicyEvaluation(item.evaluation)
  );
}

function isPolicySpec(value: unknown): value is PolicySpec {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.versionId === "string" &&
    typeof item.confidenceThreshold === "number" &&
    typeof item.ambiguousToS === "boolean"
  );
}

function isPolicyEvaluation(value: unknown): value is PolicyEvaluation {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.accepted === "boolean" &&
    Array.isArray(item.reasons) &&
    isReplayMetrics(item.baseline) &&
    isReplayMetrics(item.candidate)
  );
}

function isReplayMetrics(value: unknown): value is ReplayMetrics {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return ["totalCases", "weightedAccuracy", "sRouteRecall", "missedHighRisk", "solCalls"].every(
    (key) => typeof item[key] === "number" && Number.isFinite(item[key]),
  );
}
