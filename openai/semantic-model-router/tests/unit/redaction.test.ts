import assert from "node:assert/strict";
import test from "node:test";

import { redactText } from "../../src/security/redaction.js";

test("redacts provider, request, secret, and path details", () => {
  const raw =
    "POST https://private.example/v1 req_abcdef123 token=topsecret " +
    "sk-1234567890 /Users/private/project/file.ts";
  const safe = redactText(raw);

  for (const secret of [
    "private.example",
    "req_abcdef123",
    "topsecret",
    "sk-1234567890",
    "/Users/private",
  ]) {
    assert.equal(safe.includes(secret), false, secret);
  }
});
