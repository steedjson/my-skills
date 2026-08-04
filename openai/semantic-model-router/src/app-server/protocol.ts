export type JsonRpcId = number | string;

export interface JsonRpcRequest {
  id: JsonRpcId;
  method: string;
  params?: unknown;
}

export interface JsonRpcResponse {
  id: JsonRpcId;
  result?: unknown;
  error?: {
    code?: number;
    message?: string;
    data?: unknown;
  };
}

export interface JsonRpcNotification {
  method: string;
  params?: unknown;
}

export type JsonRpcMessage =
  | JsonRpcRequest
  | JsonRpcResponse
  | JsonRpcNotification;

export interface ModelListEntry {
  id?: string;
  model?: string;
  supportedReasoningEfforts?: Array<{
    reasoningEffort?: string;
  }>;
}

export interface ModelListResult {
  data?: ModelListEntry[];
  nextCursor?: string | null;
}

export interface ThreadStartResult {
  model?: string;
  thread?: { id?: string };
}

export interface ThreadSettings {
  model?: string;
  effort?: string | null;
}

export interface ThreadSettingsUpdatedParams {
  threadId?: string;
  threadSettings?: ThreadSettings;
}

export interface TurnItem {
  type?: string;
  text?: string;
}

export interface Turn {
  id?: string;
  status?: string;
  error?: { message?: string } | null;
  items?: TurnItem[];
}

export interface TurnCompletedParams {
  threadId?: string;
  turn?: Turn;
}

export interface TurnStartResult {
  turn?: Turn;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isJsonRpcResponse(value: unknown): value is JsonRpcResponse {
  return (
    isRecord(value) &&
    (typeof value.id === "string" || typeof value.id === "number") &&
    ("result" in value || "error" in value)
  );
}

export function isJsonRpcNotification(
  value: unknown,
): value is JsonRpcNotification {
  return isRecord(value) && typeof value.method === "string" && !("id" in value);
}
