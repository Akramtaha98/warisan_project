const baseUrl = (process.env.EVALUATION_URL || "https://warisanproject.vercel.app").replace(/\/$/, "");
const requestedLimit = Number.parseInt(process.env.EVALUATION_LIMIT || "4", 10);
const requestedCase = process.env.EVALUATION_CASE || "";

const allCases = [
  {
    id: "direct-definition",
    question: "Apakah fungsi tanda soal?",
    expectedMode: "direct",
  },
  {
    id: "hard-multi-rule-correction",
    question: "Betulkan dan jelaskan kesalahan dalam ayat 'Para pelajar-pelajar di minta untuk mengulangkaji nota-nota mereka supaya agar lulus'.",
    expectedMode: "thinking",
  },
  {
    id: "hard-ambiguity",
    question: "Mengapakah ayat 'Ali melihat lelaki dengan teropong' kabur, dan bagaimanakah ayat itu boleh diperjelas?",
    expectedMode: "thinking",
  },
  {
    id: "grounded-boundary",
    question: "Siapakah pemimpin negara yang memenangi pilihan raya terkini?",
    expectedMode: "thinking",
  },
];
const selectedCases = requestedCase
  ? allCases.filter((entry) => entry.id === requestedCase)
  : allCases;
if (!selectedCases.length) throw new Error(`Unknown EVALUATION_CASE: ${requestedCase}`);
const cases = selectedCases.slice(0, Math.max(1, Math.min(selectedCases.length, requestedLimit)));

const results = [];
for (const entry of cases) {
  const startedAt = Date.now();
  let response;
  let payload = {};
  for (let attempt = 0; attempt < 2; attempt += 1) {
    response = await fetch(`${baseUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: entry.question, history: [] }),
    });
    payload = await response.json().catch(() => ({}));
    if (response.ok) break;
    if (![429, 503].includes(response.status) || attempt === 1) break;
    await new Promise((resolve) => setTimeout(resolve, 4000));
  }
  if (!response.ok) {
    const failure = {
      id: entry.id,
      passed: false,
      status: response.status,
      error: payload.detail || "request failed",
      elapsedMs: Date.now() - startedAt,
    };
    results.push(failure);
    console.log(JSON.stringify(failure));
    continue;
  }

  const checks = {
    qwenModel: /qwen/i.test(String(payload.model || "")),
    answerPresent: String(payload.answer || "").trim().length >= 20,
    expectedMode: payload.thinking_mode === entry.expectedMode,
    scored: Number.isFinite(payload.quality_score) && payload.quality_score >= 0 && payload.quality_score <= 100,
    grounded: Array.isArray(payload.sources) && payload.sources.length >= 1,
  };
  const passed = Object.values(checks).every(Boolean);
  results.push({
    id: entry.id,
    passed,
    model: payload.model,
    thinkingMode: payload.thinking_mode,
    qualityScore: payload.quality_score,
    sourceCount: payload.sources?.length || 0,
    elapsedMs: Date.now() - startedAt,
    checks,
  });
  console.log(JSON.stringify(results.at(-1)));
}

console.log(JSON.stringify({ endpoint: baseUrl, results }, null, 2));
if (results.some((result) => !result.passed)) process.exitCode = 1;
else console.log("live-qwen3-evaluation-passed");
