import { redactText } from "../security/redaction.js";
import type { RiskTag } from "../routing/hard-rules.js";

const RISK_TAGS: ReadonlySet<RiskTag> = new Set([
  "destructive",
  "external_side_effect",
  "permission_or_security",
  "schema_or_migration",
  "credential_handling",
]);

export interface TaskPacket {
  goal: string;
  completionDefinition: string;
  declaredScope: string[];
  assumptions: string[];
  evidence: string[];
  prohibitedActions: string[];
  steps: string[];
  verification: string[];
  acceptanceCriteria: string[];
  riskTags: RiskTag[];
  approvalPoints: string[];
  majorDeviationRules: string[];
}

export function plannerPrompt(prompt: string): string {
  return [
    "You are semantic-model-router planning role.",
    "Return one JSON task packet only. Do not include chain-of-thought, secrets, full code, or a full diff.",
    "Required keys: goal, completion_definition, declared_scope, assumptions, evidence, prohibited_actions, steps, verification, acceptance_criteria, risk_tags, approval_points, major_deviation_rules.",
    "completion_definition must be one concise string; do not return an array for this field.",
    "Every array must contain concise strings. Executor must re-read repository state before editing.",
    `User task:\n${prompt}`,
  ].join("\n");
}

export function parseTaskPacket(text: string): TaskPacket | undefined {
  const value = parseJson(text);
  if (!isRecord(value)) return undefined;
  const strings = [
    "declared_scope",
    "assumptions",
    "evidence",
    "prohibited_actions",
    "steps",
    "verification",
    "acceptance_criteria",
    "approval_points",
    "major_deviation_rules",
  ];
  if (typeof value.goal !== "string" || !value.goal.trim()) return undefined;
  if (strings.some((key) => key !== "goal" && !isStringArray(value[key]))) return undefined;
  const completionDefinition = value.completion_definition;
  if (
    !(
      (typeof completionDefinition === "string" && completionDefinition.trim()) ||
      isStringArray(completionDefinition)
    )
  ) {
    return undefined;
  }
  const riskTags = value.risk_tags;
  if (!Array.isArray(riskTags) || !riskTags.every((item) => typeof item === "string" && RISK_TAGS.has(item as RiskTag))) return undefined;
  return {
    goal: clean(value.goal),
    completionDefinition:
      typeof completionDefinition === "string"
        ? clean(completionDefinition)
        : cleanArray(completionDefinition).join("; "),
    declaredScope: cleanArray(value.declared_scope),
    assumptions: cleanArray(value.assumptions),
    evidence: cleanArray(value.evidence),
    prohibitedActions: cleanArray(value.prohibited_actions),
    steps: cleanArray(value.steps),
    verification: cleanArray(value.verification),
    acceptanceCriteria: cleanArray(value.acceptance_criteria),
    riskTags: riskTags as RiskTag[],
    approvalPoints: cleanArray(value.approval_points),
    majorDeviationRules: cleanArray(value.major_deviation_rules),
  };
}

export function serializeTaskPacket(packet: TaskPacket): string {
  return JSON.stringify({
    goal: packet.goal,
    completion_definition: packet.completionDefinition,
    declared_scope: packet.declaredScope,
    assumptions: packet.assumptions,
    evidence: packet.evidence,
    prohibited_actions: packet.prohibitedActions,
    steps: packet.steps,
    verification: packet.verification,
    acceptance_criteria: packet.acceptanceCriteria,
    risk_tags: packet.riskTags,
    approval_points: packet.approvalPoints,
    major_deviation_rules: packet.majorDeviationRules,
  });
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function clean(value: string): string {
  return redactText(value).replace(/[\r\n]+/g, " ").slice(0, 1000);
}

function cleanArray(value: unknown): string[] {
  return (value as string[]).slice(0, 50).map(clean);
}
