import { boundedHistory, retrieveFixtures } from "./retrieval.js";

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

async function callQwen(messages, { fetcher, token, model, maxTokens, temperature, url, headers = {} }) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const response = await fetcher(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        ...headers,
      },
      body: JSON.stringify({
        model,
        messages,
        temperature,
        max_tokens: maxTokens,
        stream: false,
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const retryable = [429, 500, 502, 503, 504].includes(response.status);
      if (retryable && attempt < 2) {
        await new Promise((resolve) => setTimeout(resolve, 750 * 2 ** attempt));
        continue;
      }
      throw new Error(`Qwen API ${response.status}: ${payload?.error?.message || "request failed"}`);
    }
    const content = stripPrivateReasoning(payload?.choices?.[0]?.message?.content);
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
  const useOpenRouter = Boolean(env.OPENROUTER_API_KEY);
  const token = env.OPENROUTER_API_KEY || options.token || env.AI_GATEWAY_API_KEY || env.VERCEL_OIDC_TOKEN;
  if (!token) {
    const error = new Error("Pengesahan Vercel AI Gateway belum tersedia.");
    error.statusCode = 503;
    throw error;
  }
  const model = env.QWEN_MODEL || (useOpenRouter ? DEFAULT_FREE_MODEL : DEFAULT_MODEL);
  const provider = useOpenRouter
    ? {
        url: OPENROUTER_URL,
        headers: {
          "HTTP-Referer": env.PUBLIC_APP_URL || "https://warisanproject.vercel.app",
          "X-Title": "Warisan Malay Chatbot",
        },
      }
    : { url: VERCEL_GATEWAY_URL };
  const retrieval = retrieveFixtures(question, history);
  const contexts = formatContexts(retrieval.matches);
  const conversation = history.map((item) => `${item.role === "user" ? "Pengguna" : "Pembantu"}: ${item.content}`).join("\n");

  const answer = await callQwen([
    {
      role: "system",
      content: [
        "Anda ialah pembantu Bahasa Melayu Warisan. /think",
        "Jawab dalam Bahasa Melayu formal menggunakan hanya FAKTA RUJUKAN yang diberikan.",
        "Gunakan sejarah perbualan untuk memahami soalan separa atau susulan.",
        "Jika rujukan tidak menyokong jawapan, nyatakan bahawa data demo tidak mencukupi.",
        "Jangan dakwa data sintetik ini sebagai nasihat rasmi DBP. Jangan dedahkan pemikiran dalaman.",
      ].join(" "),
    },
    {
      role: "user",
      content: `SEJARAH:\n${conversation || "Tiada"}\n\nFAKTA RUJUKAN DEMO:\n${contexts}\n\nSOALAN:\n${question}`,
    },
  ], { fetcher, token, model, maxTokens: 650, temperature: 0.25, ...provider });

  let evaluation;
  try {
    const judgeText = await callQwen([
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
    ], { fetcher, token, model, maxTokens: 220, temperature: 0, ...provider });
    evaluation = parseJudgeResult(judgeText, retrieval.retrievalScore);
  } catch {
    evaluation = parseJudgeResult("{}", retrieval.retrievalScore);
    evaluation.note = "Penilaian Qwen3 tidak tersedia; skor anggaran retrieval digunakan.";
  }

  return {
    answer,
    question,
    top_score: Number(retrieval.retrievalScore.toFixed(2)),
    quality_score: evaluation.overall,
    quality_label: evaluation.label,
    quality_breakdown: evaluation.dimensions,
    evaluation_note: evaluation.note,
    used_hyde: false,
    expanded: retrieval.retrievalQuery !== question,
    question_type: retrieval.retrievalQuery !== question ? "follow_up" : "general",
    thinking_mode: "thinking",
    model,
    dataset_mode: "synthetic-demo",
    sources: retrieval.matches.map((match) => ({
      index: match.rank,
      preview: match.document.slice(0, 320),
      category: match.category,
    })),
  };
}
