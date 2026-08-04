import { redactText } from "../security/redaction.js";
import type { RiskTag } from "./hard-rules.js";

export type Route = "L" | "S";

const RISK_TAGS: ReadonlySet<RiskTag> = new Set([
  "destructive",
  "external_side_effect",
  "permission_or_security",
  "schema_or_migration",
  "credential_handling",
]);

export interface ClassifierResult {
  route: Route;
  confidence: number;
  riskTags: RiskTag[];
  ambiguity: number;
  scope: number;
  crossModule: number;
  unknownContext: number;
  reasonCodes: string[];
  userSummary: string;
}

export function classifierPrompt(prompt: string): string {
  return [
    "You are semantic-model-router classifier. Use the assigned model and reasoning effort only; do not assume a fixed provider or model family.",
    "Return JSON only. Never include chain-of-thought, secrets, code, or a full diff.",
    'Schema: {"route":"L"|"S","confidence":0..1,"risk_tags":[],"ambiguity":0..1,"scope":0..1,"cross_module":0..1,"unknown_context":0..1,"reason_codes":[string],"user_summary":string}.',
    "risk_tags may contain only: destructive, external_side_effect, permission_or_security, schema_or_migration, credential_handling. If no exact tag applies, return []. Do not invent semantic labels.",
    "Use S when uncertain, cross-module, underspecified, or requiring architectural reasoning.",
    `Task:\n${prompt}`,
  ].join("\n");
}

export function parseClassifierResult(text: string): ClassifierResult | undefined {
  const value = parseJson(text);
  if (!isRecord(value)) return undefined;
  const route = value.route;
  if (route !== "L" && route !== "S") return undefined;
  const confidence = numberInRange(value.confidence);
  const ambiguity = numberInRange(value.ambiguity);
  const scope = numberInRange(value.scope);
  const crossModule = numberInRange(value.cross_module);
  const unknownContext = numberInRange(value.unknown_context);
  if ([confidence, ambiguity, scope, crossModule, unknownContext].some((item) => item === undefined)) {
    return undefined;
  }
  if (!Array.isArray(value.risk_tags) || !value.risk_tags.every((item) => typeof item === "string")) {
    return undefined;
  }
  if (!Array.isArray(value.reason_codes) || !value.reason_codes.every((item) => typeof item === "string" && item.length <= 80)) {
    return undefined;
  }
  if (typeof value.user_summary !== "string" || !value.user_summary.trim()) return undefined;
  const rawRiskTags = value.risk_tags as string[];
  const riskTags = rawRiskTags.filter((item): item is RiskTag => RISK_TAGS.has(item as RiskTag));
  const unknownRiskTags = rawRiskTags.filter((item) => !RISK_TAGS.has(item as RiskTag));
  const reasonCodes = (value.reason_codes as string[]).map((item) =>
    redactText(item).replace(/[\r\n]+/g, " ").slice(0, 80),
  );
  if (unknownRiskTags.length) reasonCodes.push("classifier-unknown-risk-tags");
  return {
    route,
    confidence: unknownRiskTags.length ? Math.min(confidence as number, 0.5) : confidence as number,
    riskTags,
    ambiguity: unknownRiskTags.length ? Math.max(ambiguity as number, 0.8) : ambiguity as number,
    scope: scope as number,
    crossModule: crossModule as number,
    unknownContext: unknownRiskTags.length ? 1 : unknownContext as number,
    reasonCodes,
    userSummary: redactText(value.user_summary).replace(/[\r\n]+/g, " ").slice(0, 240),
  };
}

function parseJson(text: string): unknown {
  const trimmed = text.trim();
  const fenced = /^```(?:json)?\s*([\s\S]*?)\s*```$/i.exec(trimmed)?.[1];
  try {
    return JSON.parse(fenced ?? trimmed);
  } catch {
    return undefined;
  }
}

function numberInRange(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1
    ? value
    : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
