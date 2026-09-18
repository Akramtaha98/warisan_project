import assert from "node:assert/strict";
import test from "node:test";
import { createChatResponse, DEFAULT_FREE_MODEL, DEFAULT_MODEL } from "../_lib/chat-core.js";

function response(content) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ choices: [{ message: { content } }] }),
  };
}

test("Qwen3 answers from retrieved context and judges answer quality", async () => {
  const calls = [];
  const fetcher = async (_url, options) => {
    calls.push(JSON.parse(options.body));
    return calls.length === 1
      ? response("<think>private</think>'Ialah' digunakan sebelum frasa nama.")
      : response('{"overall":91,"grounding":95,"relevance":92,"completeness":84,"language":93,"note":"Tepat dan jelas."}');
  };
  const result = await createChatResponse(
    {
      question: "Dan contoh pula?",
      history: [{ role: "user", content: "Apakah perbezaan ialah dan adalah?" }],
    },
    { fetcher, env: { AI_GATEWAY_API_KEY: "test-token" } },
  );

  assert.equal(calls.length, 2);
  assert.equal(calls[0].model, DEFAULT_MODEL);
  assert.match(calls[0].messages[1].content, /Apakah perbezaan ialah dan adalah/);
  assert.doesNotMatch(result.answer, /private|think/i);
  assert.equal(result.quality_score, 91);
  assert.equal(result.quality_label, "Sangat baik");
  assert.deepEqual(result.quality_breakdown, {
    grounding: 95,
    relevance: 92,
    completeness: 84,
    language: 93,
  });
  assert.equal(result.question_type, "follow_up");
  assert.ok(result.sources.length > 0);
});

test("judge values are clamped and missing credentials fail safely", async () => {
  const fetcher = async (_url, options) => {
    const body = JSON.parse(options.body);
    return body.max_tokens > 300
      ? response("Jawapan ringkas.")
      : response('{"overall":999,"grounding":-5,"relevance":80,"completeness":70,"language":90}');
  };
  const result = await createChatResponse(
    { question: "Apakah fungsi tanda soal?" },
    { fetcher, env: {}, token: "oidc-header-token" },
  );
  assert.equal(result.quality_score, 100);
  assert.equal(result.quality_breakdown.grounding, 0);
  await assert.rejects(
    () => createChatResponse({ question: "Soalan?" }, { fetcher, env: {} }),
    /Pengesahan/,
  );
});

test("OpenRouter uses the free Qwen3 model when its key is configured", async () => {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options, body: JSON.parse(options.body) });
    return calls.length === 1
      ? response("Warisan budaya ialah peninggalan bernilai daripada generasi terdahulu.")
      : response('{"overall":88,"grounding":90,"relevance":90,"completeness":82,"language":92}');
  };

  const result = await createChatResponse(
    { question: "Apakah maksud warisan budaya?" },
    { fetcher, env: { OPENROUTER_API_KEY: "free-test-key" } },
  );

  assert.equal(result.model, DEFAULT_FREE_MODEL);
  assert.equal(calls[0].url, "https://openrouter.ai/api/v1/chat/completions");
  assert.equal(calls[0].body.model, DEFAULT_FREE_MODEL);
  assert.equal(calls[0].options.headers.Authorization, "Bearer free-test-key");
});

test("temporary provider limits are retried before succeeding", async () => {
  let calls = 0;
  const fetcher = async () => {
    calls += 1;
    if (calls < 3) {
      return {
        ok: false,
        status: 429,
        json: async () => ({ error: { message: "Provider returned error" } }),
      };
    }
    return calls === 3
      ? response("Jawapan selepas percubaan semula.")
      : response('{"overall":80,"grounding":80,"relevance":80,"completeness":80,"language":80}');
  };

  const result = await createChatResponse(
    { question: "Apakah fungsi tanda soal?" },
    { fetcher, env: { OPENROUTER_API_KEY: "free-test-key" } },
  );

  assert.equal(calls, 4);
  assert.equal(result.answer, "Jawapan selepas percubaan semula.");
});
