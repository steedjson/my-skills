const REPLACEMENTS: ReadonlyArray<[RegExp, string]> = [
  [/https?:\/\/[^\s"'<>]+/gi, "[REDACTED_URL]"],
  [/\bBearer\s+[A-Za-z0-9._~+\/-]+=*/gi, "Bearer [REDACTED]"],
  [/\bsk-[A-Za-z0-9_-]{8,}\b/g, "[REDACTED_SECRET]"],
  [/\b(?:req|request)[-_ ]?id\s*[:=]\s*[A-Za-z0-9._-]+/gi, "request-id=[REDACTED]"],
  [/\breq_[A-Za-z0-9_-]{6,}\b/g, "[REDACTED_REQUEST_ID]"],
  [/\b(api[_ -]?key|secret|password|token)\s*[:=]\s*[^\s,;]+/gi, "$1=[REDACTED]"],
  [/(?:\/Users|\/home|\/private|\/var|\/tmp)\/[A-Za-z0-9_./ -]+/g, "[REDACTED_PATH]"],
  [/[A-Za-z]:\\(?:[^\s<>:"|?*]+\\)*[^\s<>:"|?*]*/g, "[REDACTED_PATH]"],
];

export function redactText(value: string): string {
  let result = value;
  for (const [pattern, replacement] of REPLACEMENTS) {
    result = result.replace(pattern, replacement);
  }
  return result.slice(0, 1000);
}

export function safeErrorMessage(error: unknown): string {
  if (!(error instanceof Error)) return "Router operation failed";
  return redactText(error.message || "Router operation failed");
}
