import { createInterface } from "node:readline";
import type { ChildProcessWithoutNullStreams } from "node:child_process";

import { redactText } from "../security/redaction.js";
import {
  isJsonRpcNotification,
  isJsonRpcResponse,
  type JsonRpcId,
  type JsonRpcNotification,
} from "./protocol.js";

export class AppServerClientError extends Error {
  constructor(message: string) {
    super(redactText(message));
    this.name = "AppServerClientError";
  }
}

export class AppServerProtocolError extends AppServerClientError {}

type Pending = {
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
  timer: NodeJS.Timeout;
};

type NotificationWaiter = {
  predicate: (message: JsonRpcNotification) => boolean;
  resolve: (message: JsonRpcNotification) => void;
  reject: (reason: unknown) => void;
  timer: NodeJS.Timeout;
};

const BUFFERED_NOTIFICATION_METHODS = new Set([
  "thread/settings/updated",
  "turn/completed",
  "item/completed",
  "item/agentMessage/delta",
]);

export interface AppServerClientOptions {
  requestTimeoutMs?: number;
  maxBufferedNotifications?: number;
}

export class AppServerClient {
  private readonly pending = new Map<JsonRpcId, Pending>();
  private readonly waiters: NotificationWaiter[] = [];
  private readonly buffered: JsonRpcNotification[] = [];
  private readonly requestTimeoutMs: number;
  private readonly maxBufferedNotifications: number;
  private nextId = 1;
  private closed = false;
  private closeError: Error | undefined;
  private readonly lineReader;

  constructor(
    private readonly child: ChildProcessWithoutNullStreams,
    options: AppServerClientOptions = {},
  ) {
    this.requestTimeoutMs = options.requestTimeoutMs ?? 30_000;
    this.maxBufferedNotifications = options.maxBufferedNotifications ?? 128;
    this.lineReader = createInterface({ input: child.stdout });
    this.lineReader.on("line", (line) => this.handleLine(line));
    child.on("error", (error) => this.fail(error));
    child.on("close", (code, signal) => {
      this.fail(
        new AppServerClientError(
          `App Server exited (${signal ?? code ?? "unknown"})`,
        ),
      );
    });
  }

  async initialize(signal?: AbortSignal): Promise<void> {
    await this.request("initialize", {
      clientInfo: {
        name: "semantic-model-router",
        version: "0.1.0",
      },
    }, signal);
    this.notify("initialized", {});
  }

  async request<T>(method: string, params: unknown, signal?: AbortSignal): Promise<T> {
    if (this.closed) {
      throw this.closeError ?? new AppServerClientError("App Server is closed");
    }
    const id = this.nextId++;
    const message = JSON.stringify({ id, method, params });
    const promise = new Promise<unknown>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new AppServerClientError(`App Server request timed out: ${method}`));
      }, this.requestTimeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      if (signal) {
        const abort = () => {
          clearTimeout(timer);
          this.pending.delete(id);
          reject(new AppServerClientError("App Server operation cancelled"));
        };
        if (signal.aborted) abort();
        else signal.addEventListener("abort", abort, { once: true });
      }
    });
    try {
      this.child.stdin.write(`${message}\n`);
    } catch (error) {
      const pending = this.pending.get(id);
      if (pending) {
        clearTimeout(pending.timer);
        this.pending.delete(id);
        pending.reject(error);
      }
    }
    const result = await promise;
    return result as T;
  }

  notify(method: string, params: unknown): void {
    if (this.closed) return;
    this.child.stdin.write(`${JSON.stringify({ method, params })}\n`);
  }

  async waitForNotification(
    predicate: (message: JsonRpcNotification) => boolean,
    timeoutMs = this.requestTimeoutMs,
    signal?: AbortSignal,
  ): Promise<JsonRpcNotification> {
    const bufferedIndex = this.buffered.findIndex(predicate);
    if (bufferedIndex >= 0) {
      const [message] = this.buffered.splice(bufferedIndex, 1);
      if (message) return message;
    }
    if (signal?.aborted) throw new AppServerClientError("App Server operation cancelled");
    return new Promise<JsonRpcNotification>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.removeWaiter(waiter);
        reject(new AppServerClientError("App Server notification timed out"));
      }, timeoutMs);
      const waiter: NotificationWaiter = { predicate, resolve, reject, timer };
      this.waiters.push(waiter);
      const abort = () => {
        clearTimeout(timer);
        this.removeWaiter(waiter);
        reject(new AppServerClientError("App Server operation cancelled"));
      };
      signal?.addEventListener("abort", abort, { once: true });
    });
  }

  close(): void {
    this.lineReader.close();
    this.fail(new AppServerClientError("App Server client closed"));
  }

  drainNotifications(): JsonRpcNotification[] {
    return this.buffered.splice(0);
  }

  private handleLine(line: string): void {
    const trimmed = line.trim();
    if (!trimmed) return;
    let message: unknown;
    try {
      message = JSON.parse(trimmed);
    } catch {
      this.fail(new AppServerProtocolError("App Server emitted invalid JSON"));
      return;
    }
    if (!isJsonRpcResponse(message) && !isJsonRpcNotification(message)) {
      this.fail(new AppServerProtocolError("App Server emitted invalid JSON-RPC message"));
      return;
    }
    if (isJsonRpcResponse(message)) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      clearTimeout(pending.timer);
      this.pending.delete(message.id);
      if (message.error) {
        pending.reject(
          new AppServerProtocolError(message.error.message ?? "App Server request failed"),
        );
      } else {
        pending.resolve(message.result);
      }
      return;
    }
    const waiterIndex = this.waiters.findIndex((waiter) => waiter.predicate(message));
    if (waiterIndex >= 0) {
      const [waiter] = this.waiters.splice(waiterIndex, 1);
      if (waiter) {
        clearTimeout(waiter.timer);
        waiter.resolve(message);
      }
      return;
    }
    if (!BUFFERED_NOTIFICATION_METHODS.has(message.method)) return;
    this.buffered.push(message);
    if (this.buffered.length > this.maxBufferedNotifications) this.buffered.shift();
  }

  private removeWaiter(waiter: NotificationWaiter): void {
    const index = this.waiters.indexOf(waiter);
    if (index >= 0) this.waiters.splice(index, 1);
  }

  private fail(error: Error): void {
    if (this.closed) return;
    this.closed = true;
    this.closeError = error;
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
    for (const waiter of this.waiters.splice(0)) {
      clearTimeout(waiter.timer);
      waiter.reject(error);
    }
  }
}
