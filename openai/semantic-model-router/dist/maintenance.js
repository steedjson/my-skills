// src/maintenance.ts
import { randomUUID as randomUUID2 } from "node:crypto";
import {
  chmod as chmod2,
  lstat as lstat2,
  mkdir as mkdir2,
  readFile as readFile2,
  rename as rename2,
  writeFile as writeFile2
} from "node:fs/promises";
import path3 from "node:path";

// src/config.ts
import { readdirSync } from "node:fs";
import os from "node:os";
import path from "node:path";
var PLUGIN_NAME = "semantic-model-router";
var PROMPT_TTL_MS = 10 * 60 * 1e3;
var RouterConfigError = class extends Error {
  constructor(message) {
    super(message);
    this.name = "RouterConfigError";
  }
};
function routerDataDir(env = process.env, cwd = process.cwd()) {
  const configured = env.SEMANTIC_ROUTER_DATA_DIR ?? env.PLUGIN_DATA ?? env.CLAUDE_PLUGIN_DATA;
  if (configured?.trim()) return path.resolve(configured);
  const codexHome = path.resolve(env.CODEX_HOME ?? path.join(os.homedir(), ".codex"));
  const marketplace = marketplaceFromPluginCache(cwd);
  if (marketplace) {
    return path.join(codexHome, "plugins", "data", `${PLUGIN_NAME}-${marketplace}`);
  }
  const dataRoot = path.join(codexHome, "plugins", "data");
  try {
    const candidates = readdirSync(dataRoot, { withFileTypes: true }).filter(
      (entry) => entry.isDirectory() && entry.name.startsWith(`${PLUGIN_NAME}-`)
    );
    if (candidates.length === 1 && candidates[0]) {
      return path.join(dataRoot, candidates[0].name);
    }
  } catch {
  }
  throw new RouterConfigError("Router data directory is unavailable");
}
function marketplaceFromPluginCache(cwd) {
  const parts = path.resolve(cwd).split(path.sep);
  for (let index = 0; index < parts.length - 3; index += 1) {
    if (parts[index] !== "plugins" || parts[index + 1] !== "cache") continue;
    const marketplace = parts[index + 2];
    const plugin = parts[index + 3];
    if (plugin === PLUGIN_NAME && marketplace && /^[A-Za-z0-9._-]+$/.test(marketplace)) {
      return marketplace;
    }
  }
  return void 0;
}

// src/learning/policy-store.ts
import { createHash, randomUUID } from "node:crypto";
import {
  chmod,
  lstat,
  mkdir,
  readFile,
  readdir,
  rename,
  rm,
  writeFile
} from "node:fs/promises";
import path2 from "node:path";

// src/security/redaction.ts
var REPLACEMENTS = [
  [/https?:\/\/[^\s"'<>]+/gi, "[REDACTED_URL]"],
  [/\bBearer\s+[A-Za-z0-9._~+\/-]+=*/gi, "Bearer [REDACTED]"],
  [/\bsk-[A-Za-z0-9_-]{8,}\b/g, "[REDACTED_SECRET]"],
  [/\b(?:req|request)[-_ ]?id\s*[:=]\s*[A-Za-z0-9._-]+/gi, "request-id=[REDACTED]"],
  [/\breq_[A-Za-z0-9_-]{6,}\b/g, "[REDACTED_REQUEST_ID]"],
  [/\b(api[_ -]?key|secret|password|token)\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]"],
  [/(?:\/Users|\/home|\/private|\/var|\/tmp)\/[A-Za-z0-9_./ -]+/g, "[REDACTED_PATH]"],
  [/[A-Za-z]:\\(?:[^\s<>:"|?*]+\\)*[^\s<>:"|?*]*/g, "[REDACTED_PATH]"]
];
function redactText(value) {
  let result = value;
  for (const [pattern, replacement] of REPLACEMENTS) {
    result = result.replace(pattern, replacement);
  }
  return result.slice(0, 1e3);
}

// src/learning/policy-store.ts
var CANDIDATE_ID_PATTERN = /^policy-candidate-[A-Za-z0-9_-]{8,128}$/;
var VERSION_ID_PATTERN = /^[A-Za-z0-9_.-]{1,128}$/;
var WEAK_FEEDBACK_TTL_MS = 90 * 24 * 60 * 60 * 1e3;
var PolicyStoreError = class extends Error {
  constructor(message) {
    super(message);
    this.name = "PolicyStoreError";
  }
};
var BASELINE_POLICY = {
  versionId: "baseline",
  confidenceThreshold: 0.65,
  ambiguousToS: true
};
function policyDir(dataDir) {
  return path2.join(dataDir, "policies");
}
function candidatesDir(dataDir) {
  return path2.join(policyDir(dataDir), "candidates");
}
function candidatePath(dataDir, candidateId) {
  if (!CANDIDATE_ID_PATTERN.test(candidateId)) throw new PolicyStoreError("Policy candidate id is invalid");
  return path2.join(candidatesDir(dataDir), `${candidateId}.json`);
}
function hash(value) {
  return createHash("sha256").update(value).digest("hex").slice(0, 16);
}
async function ensurePrivateDirectory(directory) {
  await mkdir(directory, { recursive: true, mode: 448 });
  await chmod(directory, 448);
}
async function writePrivateJson(filePath, value) {
  await ensurePrivateDirectory(path2.dirname(filePath));
  const temporary = `${filePath}.${process.pid}.${randomUUID()}.tmp`;
  await writeFile(temporary, JSON.stringify(value), { encoding: "utf8", mode: 384 });
  await chmod(temporary, 384);
  await rename(temporary, filePath);
  await chmod(filePath, 384);
}
async function readJson(filePath) {
  try {
    const stats = await lstat(filePath);
    if (!stats.isFile() || stats.isSymbolicLink()) throw new PolicyStoreError("Policy record is not a private file");
    return JSON.parse(await readFile(filePath, "utf8"));
  } catch (error) {
    if (error instanceof PolicyStoreError) throw error;
    throw new PolicyStoreError("Policy record is missing or invalid");
  }
}
function validatePolicySpec(spec) {
  if (!VERSION_ID_PATTERN.test(spec.versionId)) throw new PolicyStoreError("Policy version id is invalid");
  if (!Number.isFinite(spec.confidenceThreshold) || spec.confidenceThreshold < 0.4 || spec.confidenceThreshold > 0.9) {
    throw new PolicyStoreError("Policy confidence threshold is outside safe bounds");
  }
  if (typeof spec.ambiguousToS !== "boolean") throw new PolicyStoreError("Policy ambiguity rule is invalid");
  return {
    versionId: redactText(spec.versionId).slice(0, 128),
    confidenceThreshold: Number(spec.confidenceThreshold.toFixed(4)),
    ambiguousToS: spec.ambiguousToS
  };
}
function evaluatePolicy(specInput) {
  const spec = validatePolicySpec(specInput);
  const baseline = evaluateReplay(BASELINE_POLICY);
  const candidate = evaluateReplay(spec);
  const reasons = [];
  if (candidate.missedHighRisk !== 0) reasons.push("missed high-risk case");
  if (candidate.sRouteRecall < 0.95) reasons.push("S-route recall below 95 percent");
  if (candidate.weightedAccuracy < baseline.weightedAccuracy) reasons.push("weighted accuracy below baseline");
  if (candidate.weightedAccuracy === baseline.weightedAccuracy && candidate.solCalls > baseline.solCalls * 0.9) {
    reasons.push("equal accuracy does not reduce Sol calls by 10 percent");
  }
  return { accepted: reasons.length === 0, reasons, baseline, candidate };
}
async function createPolicyCandidate(dataDir, now = Date.now()) {
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
      ambiguousToS: true
    },
    feedback.count,
    "deterministic-feedback",
    now
  );
}
async function createPolicyCandidateFromSpec(dataDir, specInput, strongFeedbackCount = 0, source = "manual-replay", now = Date.now()) {
  const spec = validatePolicySpec(specInput);
  const evaluation = evaluatePolicy(spec);
  const candidateId = `policy-candidate-${randomUUID()}`;
  const record = {
    version: 1,
    candidateId,
    state: evaluation.accepted ? "pending" : "rejected",
    createdAt: new Date(now).toISOString(),
    expiresAt: new Date(now + WEAK_FEEDBACK_TTL_MS).toISOString(),
    source,
    strongFeedbackCount,
    spec: { ...spec, versionId: candidateId },
    evaluation
  };
  await writePrivateJson(candidatePath(dataDir, candidateId), record);
  return record;
}
async function cleanupPolicyData(dataDir, now = Date.now()) {
  let removed = 0;
  try {
    const names = await readdir(candidatesDir(dataDir));
    for (const name of names) {
      if (!name.endsWith(".json")) continue;
      const filePath = path2.join(candidatesDir(dataDir), name);
      try {
        const value = await readJson(filePath);
        if (isPolicyCandidateRecord(value) && Date.parse(value.expiresAt) <= now && value.state !== "active") {
          await rm(filePath, { force: true });
          removed += 1;
        }
      } catch {
      }
    }
  } catch {
  }
  try {
    const names = await readdir(path2.join(dataDir, "feedback"));
    for (const name of names) {
      if (!name.endsWith(".json")) continue;
      const filePath = path2.join(dataDir, "feedback", name);
      try {
        const value = await readJson(filePath);
        if (!value || typeof value !== "object") continue;
        const item = value;
        if (item.strength === "weak" && typeof item.createdAt === "string" && Date.parse(item.createdAt) + WEAK_FEEDBACK_TTL_MS <= now) {
          await rm(filePath, { force: true });
          removed += 1;
        }
      } catch {
      }
    }
  } catch {
  }
  return removed;
}
async function readStrongFeedback(dataDir) {
  const directory = path2.join(dataDir, "feedback");
  let names;
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
      const value = await readJson(path2.join(directory, name));
      if (!value || typeof value !== "object") continue;
      const item = value;
      if (item.strength !== "strong") continue;
      count += 1;
      if (item.label === "incorrect") incorrect += 1;
    } catch {
    }
  }
  return { count, incorrect };
}
function evaluateReplay(spec) {
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
    { classifierRoute: "S", confidence: 0.6, highRisk: false, expectedRoute: "S", expectedApproval: false }
  ];
  let correct = 0;
  let expectedS = 0;
  let recalledS = 0;
  let missedHighRisk = 0;
  let solCalls = 0;
  for (const item of cases) {
    const route = item.highRisk ? "S" : item.confidence < spec.confidenceThreshold && spec.ambiguousToS ? "S" : item.classifierRoute;
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
    solCalls
  };
}
function isPolicyCandidateRecord(value) {
  if (!value || typeof value !== "object") return false;
  const item = value;
  return item.version === 1 && typeof item.candidateId === "string" && CANDIDATE_ID_PATTERN.test(item.candidateId) && typeof item.state === "string" && typeof item.createdAt === "string" && typeof item.expiresAt === "string" && typeof item.strongFeedbackCount === "number" && isPolicySpec(item.spec) && isPolicyEvaluation(item.evaluation);
}
function isPolicySpec(value) {
  if (!value || typeof value !== "object") return false;
  const item = value;
  return typeof item.versionId === "string" && typeof item.confidenceThreshold === "number" && typeof item.ambiguousToS === "boolean";
}
function isPolicyEvaluation(value) {
  if (!value || typeof value !== "object") return false;
  const item = value;
  return typeof item.accepted === "boolean" && Array.isArray(item.reasons) && isReplayMetrics(item.baseline) && isReplayMetrics(item.candidate);
}
function isReplayMetrics(value) {
  if (!value || typeof value !== "object") return false;
  const item = value;
  return ["totalCases", "weightedAccuracy", "sRouteRecall", "missedHighRisk", "solCalls"].every(
    (key) => typeof item[key] === "number" && Number.isFinite(item[key])
  );
}

// src/maintenance.ts
var WEEK_MS = 7 * 24 * 60 * 60 * 1e3;
function maintenanceDir(dataDir) {
  return path3.join(dataDir, "maintenance");
}
function statePath(dataDir) {
  return path3.join(maintenanceDir(dataDir), "state.json");
}
function resultPath(dataDir, runId) {
  return path3.join(maintenanceDir(dataDir), `${runId}.json`);
}
async function readState(dataDir) {
  try {
    const stats = await lstat2(statePath(dataDir));
    if (!stats.isFile() || stats.isSymbolicLink()) return void 0;
    const value = JSON.parse(await readFile2(statePath(dataDir), "utf8"));
    if (value.version !== 1 || typeof value.lastRunAt !== "string" || typeof value.runId !== "string") return void 0;
    return value;
  } catch {
    return void 0;
  }
}
async function writePrivateJson2(filePath, value) {
  await mkdir2(path3.dirname(filePath), { recursive: true, mode: 448 });
  await chmod2(path3.dirname(filePath), 448);
  const temporary = `${filePath}.${process.pid}.${randomUUID2()}.tmp`;
  await writeFile2(temporary, JSON.stringify(value), { encoding: "utf8", mode: 384 });
  await chmod2(temporary, 384);
  await rename2(temporary, filePath);
  await chmod2(filePath, 384);
}
async function runMaintenance(dataDir, options = {}) {
  const now = options.now ?? Date.now();
  const previous = await readState(dataDir);
  if (!options.force && previous && Date.parse(previous.lastRunAt) + WEEK_MS > now) {
    return {
      runId: previous.runId,
      status: "skipped",
      reason: "weekly maintenance window has not elapsed",
      removedRecords: 0
    };
  }
  const runId = `maintenance-${randomUUID2()}`;
  const removedRecords = await cleanupPolicyData(dataDir, now);
  const result = {
    runId,
    status: "completed",
    removedRecords
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
  await writePrivateJson2(statePath(dataDir), {
    version: 1,
    lastRunAt: new Date(now).toISOString(),
    runId
  });
  await writePrivateJson2(resultPath(dataDir, runId), result);
  return result;
}
async function main() {
  const dataDir = routerDataDir();
  const force = process.env.SEMANTIC_ROUTER_MAINTENANCE_FORCE === "1";
  const result = await runMaintenance(dataDir, { force });
  const fields = [
    `maintenance: ${result.status}`,
    `run_id: ${result.runId}`,
    `removed_records: ${result.removedRecords}`,
    ...result.candidateId ? [`candidate_id: ${result.candidateId}`, `candidate_state: ${result.candidateState}`] : [],
    ...result.reason ? [`reason: ${result.reason}`] : []
  ];
  process.stdout.write(`${fields.join("\n")}
`);
}
if (process.argv[1]?.endsWith("maintenance.js")) {
  main().catch((error) => {
    process.stderr.write(`${redactText(error instanceof Error ? error.message : String(error))}
`);
    process.exitCode = 1;
  });
}
export {
  runMaintenance
};
