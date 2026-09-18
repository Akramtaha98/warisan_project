import assert from "node:assert/strict";
import test from "node:test";
import { askQuestion, normalizeChatResponse, sendFeedback } from "../src/lib/api.js";

test("normalizes optional reasoning metadata", () => {
  const result = normalizeChatResponse({ answer: "  Jawapan.  ", thinking_mode: "thinking" });
  assert.equal(result.answer, "Jawapan.");
  assert.equal(result.thinkingMode, "thinking");
  assert.deepEqual(result.sources, []);
  assert.equal(result.topScore, null);
});

test("chat request uses the same-origin JSON API", async () => {
  const calls = [];
  const fetcher = async (...args) => {
    calls.push(args);
    return {
      ok: true,
      json: async () => ({ answer: "Bentuk yang betul ialah kerjasama." }),
    };
  };
  const result = await askQuestion("Ejaan kerjasama?", fetcher);
  assert.equal(result.answer, "Bentuk yang betul ialah kerjasama.");
  assert.equal(calls[0][0], "/api/chat");
  assert.equal(JSON.parse(calls[0][1].body).question, "Ejaan kerjasama?");
});

test("API errors expose the safe server detail", async () => {
  const fetcher = async () => ({
    ok: false,
    json: async () => ({ detail: "Sistem jawapan belum tersedia." }),
  });
  await assert.rejects(() => askQuestion("Soalan", fetcher), /belum tersedia/);
});

test("feedback sends the selected rating", async () => {
  let body;
  const fetcher = async (_url, options) => {
    body = JSON.parse(options.body);
    return { ok: true, json: async () => ({ status: "saved" }) };
  };
  await sendFeedback({ message_id: "m1", rating: "helpful" }, fetcher);
  assert.equal(body.rating, "helpful");
});
