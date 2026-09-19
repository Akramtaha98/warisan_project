import { boundedHistory, retrieveFixtures } from "./retrieval.js";
import { translateMalayLocally } from "./local-translate.js";

export const DEFAULT_MODEL = "alibaba/qwen-3-14b";
export const DEFAULT_FREE_MODEL = "qwen/qwen3.8-27b:free";
const VERCEL_GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/chat/completions";
const OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions";

function stripPrivateReasoning(value) {
  return String(value || "")
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/^\s*<\/think>\s*/i, "")
    .trim();
}

async function callQwen(messages, {
  fetcher,
  token,
  model,
  maxTokens,
  temperature,
  url,
  headers = {},
  reasoning,
  timeoutMs = 30_000,
}) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const requestBody = {
      model,
      messages,
      temperature,
      max_tokens: maxTokens,
      stream: false,
    };
    if (reasoning) requestBody.reasoning = reasoning;
    const response = await fetcher(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        ...headers,
      },
      signal: AbortSignal.timeout(timeoutMs),
      body: JSON.stringify(requestBody),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const retryable = [429, 500, 502, 503, 504].includes(response.status);
      if (retryable && attempt < 2) {
        await new Promise((resolve) => setTimeout(resolve, 750 * 2 ** attempt));
        continue;
      }
      const error = new Error(`Qwen API ${response.status}: ${payload?.error?.message || "request failed"}`);
      error.providerStatus = response.status;
      throw error;
    }
    const content = stripPrivateReasoning(payload?.choices?.[0]?.message?.content);
    if (!content && attempt < 2) {
      await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** attempt));
      continue;
    }
    if (!content) throw new Error("Qwen3 tidak menghasilkan jawapan akhir.");
    return content;
  }
  throw new Error("Qwen3 tidak tersedia selepas percubaan semula.");
}

function parseJudgeResult(text, retrievalScore) {
  const jsonText = text.match(/\{[\s\S]*\}/)?.[0];
  let parsed = {};
  try {
    parsed = JSON.parse(jsonText || "{}");
  } catch {
    parsed = {};
  }
  const clamp = (value, fallback = 0) =>
    Math.max(0, Math.min(100, Number.isFinite(Number(value)) ? Number(value) : fallback));
  const dimensions = {
    grounding: clamp(parsed.grounding, Math.round(retrievalScore * 100)),
    relevance: clamp(parsed.relevance, Math.round(retrievalScore * 100)),
    completeness: clamp(parsed.completeness, 50),
    language: clamp(parsed.language, 70),
  };
  const calculated = Math.round(
    dimensions.grounding * 0.4 +
    dimensions.relevance * 0.3 +
    dimensions.completeness * 0.2 +
    dimensions.language * 0.1,
  );
  const overall = clamp(parsed.overall, calculated);
  return {
    overall: Math.round(overall),
    label: overall >= 85 ? "Sangat baik" : overall >= 70 ? "Baik" : overall >= 50 ? "Sederhana" : "Perlu semakan",
    dimensions,
    note: String(parsed.note || "Skor automatik Qwen3; semakan manusia masih disyorkan.").slice(0, 240),
  };
}

function formatContexts(matches) {
  return matches.map((match, index) => `[${index + 1}] ${match.document}`).join("\n\n");
}

function normalizeFeedbackMemory(items) {
  if (!Array.isArray(items)) return [];
  return items.slice(0, 6).flatMap((item) => {
    const rating = item?.rating;
    const question = String(item?.question || "").replace(/\s+/g, " ").trim().slice(0, 2000);
    const answer = String(item?.answer || "").replace(/\s+/g, " ").trim().slice(0, 4000);
    const correction = String(item?.correction || "").replace(/\s+/g, " ").trim().slice(0, 2000);
    if (!["helpful", "unhelpful"].includes(rating) || !question || !answer) return [];
    if (rating === "unhelpful" && correction.length < 3) return [];
    return [{ rating, question, answer, correction }];
  });
}

function feedbackSimilarity(left, right) {
  const tokenize = (value) => new Set(String(value || "").toLocaleLowerCase("ms").match(/[\p{L}\p{N}]{3,}/gu) || []);
  const a = tokenize(left);
  const b = tokenize(right);
  if (!a.size || !b.size) return 0;
  let shared = 0;
  for (const token of a) if (b.has(token)) shared += 1;
  return shared / Math.max(1, Math.min(a.size, b.size));
}

function formatFeedbackMemory(items) {
  if (!items.length) return "Tiada";
  return items.map((item, index) => item.rating === "helpful"
    ? `[${index + 1}] DISUKAI — Soalan: ${item.question}\nJawapan terdahulu: ${item.answer}`
    : `[${index + 1}] PERLU DIBETULKAN — Soalan: ${item.question}\nJawapan ditolak: ${item.answer}\nPembetulan pengguna: ${item.correction}`,
  ).join("\n\n");
}

function createDatasetFallback(question, retrieval, routing, feedbackMemory = []) {
  const isGreeting = /^(hi|hai|hello|helo|salam|assalamualaikum)[!. ]*$/i.test(question);
  if (isGreeting) {
    return {
      content: "Hai! Saya **Warisan**, pembantu Bahasa Melayu. Anda boleh bertanya tentang ejaan, tatabahasa, istilah, tanda baca atau penggunaan kata.",
      model: "local-dataset",
      provider: "local-dataset-fallback",
      fallback: true,
      greeting: true,
    };
  }

  const learnedCorrection = feedbackMemory.find((item) =>
    item.rating === "unhelpful" && item.correction && feedbackSimilarity(question, item.question) >= 0.75,
  );
  if (learnedCorrection) {
    return {
      content: `${learnedCorrection.correction}\n\n*Jawapan ini menggunakan pembetulan yang anda simpan sebelum ini.*`,
      model: "local-feedback-memory",
      provider: "browser-feedback-memory",
      fallback: true,
      greeting: false,
      feedbackApplied: true,
    };
  }

  const topMatch = retrieval.matches[0];
  const supported = topMatch && topMatch.lexicalScore > 0 && retrieval.retrievalScore >= 0.12;
  if (!supported) {
    return {
      content: [
        "Maaf, dataset demonstrasi belum mempunyai maklumat yang cukup tepat untuk menjawab soalan itu.",
        "Cuba tanyakan tentang ejaan, tatabahasa, kata sendi, imbuhan, tanda baca atau peribahasa Bahasa Melayu.",
      ].join("\n\n"),
      model: "local-dataset",
      provider: "local-dataset-fallback",
      fallback: true,
      greeting: false,
    };
  }

  const prefix = routing.hard
    ? `Saya menyemak ${retrieval.matches.length} rekod dataset yang paling berkaitan. Berdasarkan padanan terkuat:`
    : "Berdasarkan rekod dataset yang paling berkaitan:";
  return {
    content: `${prefix}\n\n${topMatch.answer}`,
    model: "local-dataset",
    provider: "local-dataset-fallback",
    fallback: true,
    greeting: false,
  };
}

function evaluateDatasetFallback(retrieval, supported) {
  const relevance = supported ? Math.max(35, Math.round(retrieval.retrievalScore * 100)) : 10;
  return parseJudgeResult(JSON.stringify({
    grounding: supported ? 100 : 20,
    relevance,
    completeness: supported ? 72 : 20,
    language: 90,
    note: supported
      ? "Jawapan diambil terus daripada rekod dataset kerana Qwen3 tidak tersedia."
      : "Tiada padanan dataset yang cukup kuat dan Qwen3 tidak tersedia.",
  }), retrieval.retrievalScore);
}

export function classifyQuestion(question, matches = [], isFollowUp = false) {
  const value = String(question || "").toLowerCase();
  const topMatch = matches[0];
  let complexity = 0;
  if (/\b(bandingkan|betulkan|baiki|jelaskan|terangkan|tukarkan|susun|mengapakah)\b/i.test(value)) complexity += 2;
  if (/\b(kemudian|serta jelaskan|semua kesalahan|lebih tepat|perbezaannya)\b/i.test(value)) complexity += 2;
  if ((value.match(/\b(dan|serta|atau)\b/g) || []).length >= 2) complexity += 1;
  if (value.length >= 120) complexity += 1;
  if (topMatch?.difficulty === "hard" || topMatch?.category?.startsWith("penaakulan_")) complexity += 3;

  let type = "general";
  if (isFollowUp) type = "follow_up";
  else if (/\b(bandingkan|perbezaan|beza)\b/i.test(value)) type = "comparison";
  else if (/\b(betulkan|baiki|salah|tepat)\b/i.test(value)) type = "correction";
  else if (/\b(tukarkan|susun|kemudian|dan.*dan)\b/i.test(value)) type = "multi_part";
  else if (/^(apa|apakah)\s+(maksud|fungsi)/i.test(value)) type = "definition";
  else if (/\b(ejaan|ditulis|baku)\b/i.test(value)) type = "spelling_or_term";

  return {
    type,
    hard: complexity >= 3,
    complexity,
  };
}

export async function createTranslationResponse(body, options = {}) {
  const fetcher = options.fetcher || fetch;
  const env = options.env || process.env;
  const text = String(body?.text || "").replace(/\s+/g, " ").trim();
  if (text.length < 2 || text.length > 4000) {
    const error = new Error("Teks terjemahan mestilah antara 2 hingga 4000 aksara.");
    error.statusCode = 422;
    throw error;
  }

  const useOpenRouter = Boolean(env.OPENROUTER_API_KEY);
  const token = env.OPENROUTER_API_KEY || options.token || env.AI_GATEWAY_API_KEY || env.VERCEL_OIDC_TOKEN;
  if (!token) return {
    translation: translateMalayLocally(text),
    model: "local-rule-based",
    provider: "local-translation-fallback",
    fallback_used: true,
  };
  const model = useOpenRouter ? env.QWEN_MODEL || DEFAULT_FREE_MODEL : env.QWEN_GATEWAY_MODEL || DEFAULT_MODEL;
  const provider = useOpenRouter
    ? {
        name: "openrouter-free",
        url: OPENROUTER_URL,
        headers: {
          "HTTP-Referer": env.PUBLIC_APP_URL || "https://warisanproject.vercel.app",
          "X-Title": "Warisan Malay Chatbot",
        },
      }
    : { name: "vercel-ai-gateway", url: VERCEL_GATEWAY_URL };

  try {
    const translation = await callQwen([
    {
      role: "system",
      content: "You are a professional Malay-to-English translator. /no_think Translate faithfully into clear natural English. Preserve examples and punctuation. Return only the English translation without commentary or quotation marks.",
    },
    { role: "user", content: text },
  ], {
    fetcher,
    token,
    model,
    maxTokens: 750,
    temperature: 0.1,
    timeoutMs: 28_000,
    url: provider.url,
    headers: provider.headers,
  });

    return { translation, model, provider: provider.name, fallback_used: false };
  } catch {
    return {
      translation: translateMalayLocally(text),
      model: "local-rule-based",
      provider: "local-translation-fallback",
      fallback_used: true,
    };
  }
}

export async function createChatResponse(body, options = {}) {
  const fetcher = options.fetcher || fetch;
  const env = options.env || process.env;
  const question = String(body?.question || "").replace(/\s+/g, " ").trim();
  if (question.length < 2 || question.length > 2000) {
    const error = new Error("Sila masukkan soalan antara 2 hingga 2000 aksara.");
    error.statusCode = 422;
    throw error;
  }
  const history = boundedHistory(body?.history);
  const feedbackMemory = normalizeFeedbackMemory(body?.feedback_memory);
  const requestedReasoningMode = body?.reasoning_mode === "deep" ? "deep" : "auto";
  const useOpenRouter = Boolean(env.OPENROUTER_API_KEY);
  const gatewayToken = options.token || env.AI_GATEWAY_API_KEY || env.VERCEL_OIDC_TOKEN;
  const providers = [];
  if (useOpenRouter) {
    providers.push({
      name: "openrouter-free",
      token: env.OPENROUTER_API_KEY,
      model: env.QWEN_MODEL || DEFAULT_FREE_MODEL,
      url: OPENROUTER_URL,
      headers: {
        "HTTP-Referer": env.PUBLIC_APP_URL || "https://warisanproject.vercel.app",
        "X-Title": "Warisan Malay Chatbot",
      },
    });
  }
  if (!useOpenRouter && gatewayToken) {
    providers.push({
      name: "vercel-ai-gateway",
      token: gatewayToken,
      model: env.QWEN_GATEWAY_MODEL || DEFAULT_MODEL,
      url: VERCEL_GATEWAY_URL,
    });
  }
  const callAvailableQwen = async (messages, settings, preferredModel) => {
    const orderedProviders = preferredModel
      ? [...providers].sort((provider) => provider.model === preferredModel ? -1 : 1)
      : providers;
    let lastError;
    for (const provider of orderedProviders) {
      try {
        const content = await callQwen(messages, {
          fetcher,
          ...settings,
          ...provider,
          reasoning: provider.name === "openrouter-free" ? settings.reasoning : undefined,
        });
        return { content, model: provider.model, provider: provider.name };
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError;
  };
  let retrieval = retrieveFixtures(question, history, 4);
  let routing = classifyQuestion(question, retrieval.matches, retrieval.retrievalQuery !== question);
  if (requestedReasoningMode === "deep") routing = { ...routing, hard: true };
  if (routing.hard) {
    retrieval = retrieveFixtures(question, history, 6);
    routing = classifyQuestion(question, retrieval.matches, retrieval.retrievalQuery !== question);
    if (requestedReasoningMode === "deep") routing = { ...routing, hard: true };
  }
  const contexts = formatContexts(retrieval.matches);
  const feedbackGuide = formatFeedbackMemory(feedbackMemory);
  const conversation = history.map((item) => `${item.role === "user" ? "Pengguna" : "Pembantu"}: ${item.content}`).join("\n");
  const reasoningDirective = routing.hard ? "/think" : "/no_think";

  let answerResult;
  try {
    if (providers.length === 0) throw new Error("Tiada penyedia Qwen3 dikonfigurasikan.");
    answerResult = await callAvailableQwen([
    {
      role: "system",
      content: [
        `Anda ialah pembantu Bahasa Melayu Warisan. ${reasoningDirective}`,
        "Jawab dalam Bahasa Melayu formal menggunakan hanya FAKTA RUJUKAN yang diberikan.",
        "Gunakan sejarah perbualan untuk memahami soalan separa atau susulan.",
        routing.hard
          ? "Soalan ini memerlukan penaakulan lebih teliti. Analisis semua bahagian dan semak setiap pembetulan terhadap rujukan sebelum memberikan jawapan akhir."
          : "Soalan ini langsung. Berikan jawapan ringkas, tepat dan mudah difahami.",
        "Jika rujukan tidak menyokong jawapan, nyatakan bahawa data demo tidak mencukupi.",
        "Gunakan maklum balas terdahulu sebagai panduan gaya dan pembetulan, bukan sebagai sumber fakta. Utamakan fakta rujukan jika bercanggah.",
        "Jangan dakwa data sintetik ini sebagai nasihat rasmi DBP. Jangan dedahkan pemikiran dalaman.",
      ].join(" "),
    },
    {
      role: "user",
      content: `SEJARAH:\n${conversation || "Tiada"}\n\nMAKLUM BALAS TERDAHULU:\n${feedbackGuide}\n\nFAKTA RUJUKAN DEMO:\n${contexts}\n\nSOALAN:\n${question}`,
    },
  ], {
    maxTokens: routing.hard ? 1000 : 550,
    temperature: routing.hard ? 0.2 : 0.15,
    reasoning: routing.hard && useOpenRouter ? { effort: "medium", exclude: true } : undefined,
    timeoutMs: routing.hard ? 38_000 : 28_000,
  });
  } catch {
    answerResult = createDatasetFallback(question, retrieval, routing, feedbackMemory);
  }
  const answer = answerResult.content;

  let evaluation;
  if (answerResult.fallback) {
    evaluation = evaluateDatasetFallback(retrieval, !answerResult.greeting && retrieval.matches[0]?.lexicalScore > 0 && retrieval.retrievalScore >= 0.12);
  } else try {
    const judgeResult = await callAvailableQwen([
      {
        role: "system",
        content: "Anda penilai jawapan Bahasa Melayu. /no_think Nilai hanya berdasarkan rujukan. Pulangkan JSON sah sahaja.",
      },
      {
        role: "user",
        content: [
          `SOALAN: ${question}`,
          `RUJUKAN: ${contexts}`,
          `JAWAPAN: ${answer}`,
          'Pulangkan {"overall":0-100,"grounding":0-100,"relevance":0-100,"completeness":0-100,"language":0-100,"note":"ringkas"}.',
        ].join("\n\n"),
      },
    ], { maxTokens: 220, temperature: 0, timeoutMs: 12_000 }, answerResult.model);
    evaluation = parseJudgeResult(judgeResult.content, retrieval.retrievalScore);
  } catch {
    evaluation = parseJudgeResult("{}", retrieval.retrievalScore);
    evaluation.note = "Penilaian Qwen3 tidak tersedia; skor anggaran retrieval digunakan.";
  }

  return {
    answer,
    question,
    top_score: Number(retrieval.retrievalScore.toFixed(2)),
    quality_score: answerResult.greeting ? null : evaluation.overall,
    quality_label: answerResult.greeting ? "" : evaluation.label,
    quality_breakdown: answerResult.greeting ? null : evaluation.dimensions,
    evaluation_note: answerResult.greeting ? "Ucapan diproses secara setempat." : evaluation.note,
    used_hyde: false,
    expanded: retrieval.retrievalQuery !== question,
    question_type: routing.type,
    thinking_mode: answerResult.fallback ? "retrieval" : routing.hard ? "thinking" : "direct",
    reasoning_depth: answerResult.fallback ? "dataset" : routing.hard ? "deep" : "standard",
    reasoning_requested: requestedReasoningMode === "deep",
    fallback_used: Boolean(answerResult.fallback),
    feedback_memory_used: answerResult.feedbackApplied ? 1 : feedbackMemory.length,
    context_count: answerResult.greeting ? 0 : retrieval.matches.length,
    model: answerResult.model,
    provider: answerResult.provider,
    dataset_mode: "synthetic-demo",
    sources: (answerResult.greeting ? [] : retrieval.matches).map((match) => ({
      index: match.rank,
      preview: match.document.slice(0, 320),
      category: match.category,
    })),
  };
}
