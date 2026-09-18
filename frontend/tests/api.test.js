import assert from "node:assert/strict";
import test from "node:test";
import { askQuestion, normalizeChatResponse, sendFeedback } from "../src/lib/api.js";

test("normalizes optional reasoning metadata", () => {
  const result = normalizeChatResponse({ answer: "  Jawapan.  ", thinking_mode: "thinking" });
  assert.equal(result.answer, "Jawapan.");
  assert.equal(result.thinkingMode, "thinking");
  assert.deepEqual(result.sources, []);
  assert.equal(result.topScore, null);
  assert.equal(result.qualityScore, null);
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
  const history = [{ role: "user", content: "Tentang ejaan." }];
  const result = await askQuestion("Ejaan kerjasama?", history, fetcher);
  assert.equal(result.answer, "Bentuk yang betul ialah kerjasama.");
  assert.equal(calls[0][0], "/api/chat");
  assert.equal(JSON.parse(calls[0][1].body).question, "Ejaan kerjasama?");
  assert.deepEqual(JSON.parse(calls[0][1].body).history, history);
});

test("API errors expose the safe server detail", async () => {
  const fetcher = async () => ({
    ok: false,
    json: async () => ({ detail: "Sistem jawapan belum tersedia." }),
  });
  await assert.rejects(() => askQuestion("Soalan", [], fetcher), /belum tersedia/);
});

test("normalizes the Qwen3 answer-quality assessment", () => {
  const result = normalizeChatResponse({
    answer: "Jawapan.",
    quality_score: 88,
    quality_label: "Sangat baik",
    quality_breakdown: { grounding: 90, relevance: 87, completeness: 82, language: 94 },
    evaluation_note: "Tepat.",
  });
  assert.equal(result.qualityScore, 88);
  assert.equal(result.qualityLabel, "Sangat baik");
  assert.equal(result.qualityBreakdown.grounding, 90);
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
