import dataset from "../../app/sample_data/malay_qa.json" with { type: "json" };

const STOPWORDS = new Set([
  "adakah", "akan", "apa", "apakah", "atau", "antara", "bagai", "bagaimana",
  "bagi", "bahasa", "boleh", "dan", "dengan", "di", "dalam", "itu",
  "contoh", "ialah", "juga", "ke", "kepada", "lagi", "mana", "melayu", "oleh",
  "pada", "perbezaan", "pula", "saya", "sebagai", "seperti", "serta", "soalan", "tersebut",
  "tidak", "untuk", "yang",
]);

export const records = dataset.records;

export function normalizeText(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, " ")
    .trim();
}

export function meaningfulTerms(value) {
  return normalizeText(value)
    .split(/\s+/)
    .filter((term) => term.length > 1 && !STOPWORDS.has(term));
}

export function boundedHistory(history) {
  if (!Array.isArray(history)) return [];
  return history
    .slice(-6)
    .filter((item) => item && ["user", "assistant"].includes(item.role))
    .map((item) => ({
      role: item.role,
      content: String(item.content || "").replace(/\s+/g, " ").trim().slice(0, 600),
    }))
    .filter((item) => item.content.length > 0);
}

export function buildRetrievalQuery(question, history = []) {
  const cleanQuestion = String(question || "").replace(/\s+/g, " ").trim();
  const terms = meaningfulTerms(cleanQuestion);
  const looksLikeFollowUp =
    terms.length < 2 ||
    /^(dan|kalau|bagaimana|kenapa|yang|itu|ini|pula|contoh|lagi)\b/i.test(cleanQuestion);
  if (!looksLikeFollowUp) return cleanQuestion;

  const previousUser = [...boundedHistory(history)]
    .reverse()
    .find((item) => item.role === "user");
  return previousUser ? `${previousUser.content} ${cleanQuestion}` : cleanQuestion;
}

function candidateScore(query, record) {
  const queryTerms = meaningfulTerms(query);
  const question = normalizeText(record.question);
  const answer = normalizeText(record.answer);
  const category = normalizeText(record.category.replaceAll("_", " "));
  const candidateTerms = new Set(`${question} ${answer} ${category}`.split(/\s+/));
  let score = 0;

  for (const term of queryTerms) {
    if (candidateTerms.has(term)) score += 3;
    else if ([...candidateTerms].some((candidate) =>
      candidate.startsWith(term) || (candidate.length >= 4 && term.startsWith(candidate)))) score += 1;
    if (question.includes(term)) score += 1;
  }
  if (question.includes(normalizeText(query))) score += 8;
  return score;
}

export function retrieveFixtures(question, history = [], limit = 4) {
  const retrievalQuery = buildRetrievalQuery(question, history);
  const ranked = records
    .map((record) => ({ record, score: candidateScore(retrievalQuery, record) }))
    .sort((left, right) => right.score - left.score || left.record.id.localeCompare(right.record.id))
    .slice(0, Math.max(1, Math.min(limit, 6)));
  const maxPossible = Math.max(1, meaningfulTerms(retrievalQuery).length * 4 + 8);
  const retrievalScore = Math.max(0, Math.min(1, ranked[0].score / maxPossible));
  return {
    retrievalQuery,
    retrievalScore,
    matches: ranked.map(({ record, score }, index) => ({
      ...record,
      rank: index + 1,
      lexicalScore: score,
      document: `Soalan: ${record.question}\nJawapan: ${record.answer}`,
    })),
  };
}
