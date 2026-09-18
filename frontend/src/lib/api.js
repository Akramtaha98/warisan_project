async function parseResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Permintaan tidak dapat diproses. Sila cuba lagi.");
  }
  return payload;
}

export function normalizeChatResponse(payload) {
  return {
    answer: String(payload?.answer || "").trim(),
    question: String(payload?.question || "").trim(),
    topScore: typeof payload?.top_score === "number" ? payload.top_score : null,
    usedHyde: Boolean(payload?.used_hyde),
    expanded: Boolean(payload?.expanded),
    questionType: payload?.question_type || "general",
    thinkingMode: payload?.thinking_mode || "direct",
    qualityScore: typeof payload?.quality_score === "number" ? payload.quality_score : null,
    qualityLabel: payload?.quality_label || "",
    qualityBreakdown: payload?.quality_breakdown || null,
    evaluationNote: payload?.evaluation_note || "",
    datasetMode: payload?.dataset_mode || "production",
    model: payload?.model || "",
    sources: Array.isArray(payload?.sources) ? payload.sources : [],
  };
}

export async function askQuestion(question, history = [], fetcher = fetch) {
  const response = await fetcher("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
  });
  return normalizeChatResponse(await parseResponse(response));
}

export async function getHealth(fetcher = fetch) {
  const response = await fetcher("/api/health");
  return parseResponse(response);
}

export async function sendFeedback(payload, fetcher = fetch) {
  const response = await fetcher("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}
