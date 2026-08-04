import { redactText } from "../security/redaction.js";

export type ReviewStatus = "pass" | "repair" | "block";

export interface ReviewResult {
  status: ReviewStatus;
  majorDeviation: boolean;
  issues: string[];
  summary: string;
}

export function reviewerPrompt(task: string, packet: string, execution: string): string {
  return [
    "You are independent Sol reviewer for semantic-model-router.",
    "Return JSON only: {status:\"pass\"|\"repair\"|\"block\",major_deviation:boolean,issues:string[],summary:string}.",
    "Use repair for fixable acceptance failures, block for unsafe or impossible work, and major_deviation when scope/public API/schema/permission/security behavior diverged.",
    `Original task:\n${task}`,
    `Task packet:\n${packet}`,
    `Executor report:\n${execution}`,
  ].join("\n");
}

export function parseReviewResult(text: string): ReviewResult | undefined {
  const value = parseJson(text);
  if (!isRecord(value)) return undefined;
  if (value.status !== "pass" && value.status !== "repair" && value.status !== "block") return undefined;
  if (typeof value.major_deviation !== "boolean") return undefined;
  if (!Array.isArray(value.issues) || !value.issues.every((item) => typeof item === "string")) return undefined;
  if (typeof value.summary !== "string" || !value.summary.trim()) return undefined;
  return {
    status: value.status,
    majorDeviation: value.major_deviation,
    issues: value.issues.slice(0, 20).map((item) => clean(item)),
    summary: clean(value.summary),
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function clean(value: string): string {
  return redactText(value).replace(/[\r\n]+/g, " ").slice(0, 1000);
}
