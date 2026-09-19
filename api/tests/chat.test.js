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
  assert.equal(result.thinking_mode, "direct");
  assert.equal(result.reasoning_depth, "standard");
  assert.match(calls[0].messages[0].content, /\/no_think/);
  assert.ok(result.sources.length > 0);
});

test("hard multi-rule questions use Qwen3 thinking mode and six references", async () => {
  const calls = [];
  const fetcher = async (_url, options) => {
    const body = JSON.parse(options.body);
    calls.push(body);
    return calls.length === 1
      ? response("Ayat yang betul ialah 'Para pelajar diminta mengulang kaji nota mereka supaya lulus.'")
      : response('{"overall":94,"grounding":96,"relevance":95,"completeness":92,"language":93,"note":"Semua pembetulan disokong rujukan."}');
  };

  const result = await createChatResponse(
    { question: "Betulkan dan jelaskan kesalahan dalam ayat 'Para pelajar-pelajar di minta untuk mengulangkaji nota-nota mereka supaya agar lulus'." },
    { fetcher, env: { OPENROUTER_API_KEY: "free-test-key" } },
  );

  assert.equal(calls[0].max_tokens, 1000);
  assert.deepEqual(calls[0].reasoning, { effort: "medium", exclude: true });
  assert.match(calls[0].messages[0].content, /\/think/);
  assert.match(calls[0].messages[0].content, /penaakulan lebih teliti/i);
  assert.equal(result.thinking_mode, "thinking");
  assert.equal(result.reasoning_depth, "deep");
  assert.equal(result.question_type, "correction");
  assert.equal(result.context_count, 6);
  assert.equal(result.sources.length, 6);
});

test("the user can force deep reasoning for a simple question", async () => {
  const calls = [];
  const fetcher = async (_url, options) => {
    calls.push(JSON.parse(options.body));
    return calls.length === 1
      ? response("Tanda soal digunakan pada akhir ayat tanya selepas semakan rujukan.")
      : response('{"overall":92,"grounding":94,"relevance":93,"completeness":88,"language":94}');
  };

  const result = await createChatResponse(
    { question: "Apakah fungsi tanda soal?", reasoning_mode: "deep" },
    { fetcher, env: { OPENROUTER_API_KEY: "free-test-key" } },
  );

  assert.equal(calls[0].max_tokens, 1000);
  assert.match(calls[0].messages[0].content, /\/think/);
  assert.equal(result.thinking_mode, "thinking");
  assert.equal(result.reasoning_requested, true);
  assert.equal(result.context_count, 6);
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
  assert.equal(calls[0].body.reasoning, undefined);
  assert.equal(calls[0].options.headers.Authorization, "Bearer free-test-key");
});

test("empty thinking responses are retried before returning the final answer", async () => {
  let calls = 0;
  const fetcher = async (_url, options) => {
    calls += 1;
    const body = JSON.parse(options.body);
    if (calls === 1) return response("");
    if (body.max_tokens > 300) return response("Ayat itu dibetulkan selepas semakan teliti.");
    return response('{"overall":86,"grounding":88,"relevance":87,"completeness":83,"language":90}');
  };

  const result = await createChatResponse(
    { question: "Betulkan dan jelaskan semua kesalahan dalam ayat ini supaya lebih tepat." },
    { fetcher, env: { OPENROUTER_API_KEY: "free-test-key" } },
  );

  assert.equal(calls, 3);
  assert.equal(result.answer, "Ayat itu dibetulkan selepas semakan teliti.");
  assert.equal(result.thinking_mode, "thinking");
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
