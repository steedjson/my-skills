import type { RiskTag } from "./hard-rules.js";
import type { Route, ClassifierResult } from "./classifier.js";

export interface RouteDecision {
  route: Route;
  riskTags: RiskTag[];
  requiresApproval: boolean;
  reasonCodes: string[];
  summary: string;
}

export function decideRoute(input: {
  override?: Route;
  hardRiskTags: RiskTag[];
  classifier?: ClassifierResult;
  approved?: boolean;
  confidenceThreshold?: number;
  ambiguousToS?: boolean;
}): RouteDecision {
  if (input.hardRiskTags.length) {
    return {
      route: "S",
      riskTags: input.hardRiskTags,
      requiresApproval: input.approved !== true,
      reasonCodes: ["hard-risk", ...input.hardRiskTags],
      summary: input.approved === true
        ? "hard-risk approved; continue through bounded S workflow"
        : "hard-risk requires approval before execution",
    };
  }
  if (input.override) {
    return {
      route: input.override,
      riskTags: [],
      requiresApproval: false,
      reasonCodes: ["explicit-override"],
      summary: `explicit @${input.override === "S" ? "sol" : "luna"} override`,
    };
  }
  if (!input.classifier) {
    return {
      route: "S",
      riskTags: [],
      requiresApproval: false,
      reasonCodes: ["classifier-uncertain"],
      summary: "classifier unavailable or uncertain; fail closed to S",
    };
  }
  if (input.classifier.riskTags.length) {
    return {
      route: "S",
      riskTags: input.classifier.riskTags,
      requiresApproval: input.approved !== true,
      reasonCodes: ["classifier-risk", ...input.classifier.riskTags],
      summary: input.approved === true
        ? "classifier risk approved; continue through bounded S workflow"
        : "classifier detected risk; approval required before execution",
    };
  }
  const lowConfidence = input.classifier.confidence < (input.confidenceThreshold ?? 0.65);
  const route = lowConfidence && input.ambiguousToS !== false ? "S" : input.classifier.route;
  return {
    route,
    riskTags: input.classifier.riskTags,
    requiresApproval: false,
    reasonCodes: lowConfidence
      ? ["low-confidence", ...input.classifier.reasonCodes]
      : input.classifier.reasonCodes,
    summary: input.classifier.userSummary,
  };
}
