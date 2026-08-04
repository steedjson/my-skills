#!/usr/bin/env node
import fs from "node:fs";

const logPath = process.env.FAKE_APP_SERVER_LOG;
const markerPath = process.env.FAKE_APP_SERVER_MARKER;
const models = JSON.parse(
  process.env.FAKE_APP_SERVER_MODELS ??
    JSON.stringify([
      {
        id: "gpt-5.6-luna",
        model: "gpt-5.6-luna",
        supportedReasoningEfforts: [
          { reasoningEffort: "low" },
          { reasoningEffort: "max" },
        ],
      },
      {
        id: "gpt-5.6-sol",
        model: "gpt-5.6-sol",
        supportedReasoningEfforts: [{ reasoningEffort: "xhigh" }],
      },
    ]),
);

let threadId = "fake-thread-1";
let turnId = "fake-turn-1";

function log(value) {
  if (logPath) fs.appendFileSync(logPath, `${JSON.stringify(value)}\n`);
}

function send(value) {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

process.on("SIGTERM", () => {
  if (markerPath) fs.writeFileSync(markerPath, "terminated\n");
  process.exit(0);
});

process.stdin.setEncoding("utf8");
let pending = "";
process.stdin.on("data", (chunk) => {
  pending += chunk;
  let newline;
  while ((newline = pending.indexOf("\n")) >= 0) {
    const line = pending.slice(0, newline).trim();
    pending = pending.slice(newline + 1);
    if (!line) continue;
    const request = JSON.parse(line);
    log(request);
    if (request.method === "initialize") {
      send({ id: request.id, result: { userAgent: "fake", platformFamily: "unix", platformOs: "macos", codexHome: "/tmp" } });
    } else if (request.method === "model/list") {
      send({ id: request.id, result: { data: models, nextCursor: null } });
    } else if (request.method === "thread/start") {
      threadId = `fake-thread-${Date.now()}`;
      send({ id: request.id, result: { model: request.params.model, thread: { id: threadId } } });
    } else if (request.method === "thread/settings/update") {
      send({ id: request.id, result: {} });
      send({
        method: "thread/settings/updated",
        params: {
          threadId: request.params.threadId,
          threadSettings: { model: request.params.model, effort: request.params.effort },
        },
      });
    } else if (request.method === "turn/start") {
      turnId = `fake-turn-${Date.now()}`;
      send({ id: request.id, result: { turn: { id: turnId, status: "inProgress" } } });
      if (process.env.FAKE_APP_SERVER_HANG !== "1") {
        const failed = process.env.FAKE_APP_SERVER_FAIL === "1";
        const inputText = request.params.input?.find((item) => item.type === "text")?.text ?? "";
        let responseText = process.env.FAKE_APP_SERVER_TURN_TEXT ?? "fake result";
        if (inputText.includes("semantic-model-router classifier")) {
          responseText = JSON.stringify({
            route: "L",
            confidence: 0.96,
            risk_tags: [],
            ambiguity: 0.1,
            scope: 0.2,
            cross_module: 0.1,
            unknown_context: 0.1,
            reason_codes: ["fake-test"],
            user_summary: "single scoped task",
          });
        } else if (inputText.includes("Sol planner")) {
          responseText = JSON.stringify({
            goal: "complete task",
            completion_definition: "verification passes",
            declared_scope: ["src"],
            assumptions: ["current state is readable"],
            evidence: ["user task"],
            prohibited_actions: ["destructive side effects"],
            steps: ["inspect", "implement", "verify"],
            verification: ["tests"],
            acceptance_criteria: ["task complete"],
            risk_tags: [],
            approval_points: [],
            major_deviation_rules: ["stop on scope expansion"],
          });
        } else if (inputText.includes("independent Sol reviewer")) {
          responseText = JSON.stringify({
            status: "pass",
            major_deviation: false,
            issues: [],
            summary: "fake review passed",
          });
        }
        send({
          method: "turn/completed",
          params: {
            threadId: request.params.threadId,
            turn: failed
              ? { id: turnId, status: "failed", error: { message: "provider request id=req_secret https://private.example" } }
              : { id: turnId, status: "completed", items: [{ id: "message-1", type: "agentMessage", text: responseText }] },
          },
        });
      }
    }
  }
});
