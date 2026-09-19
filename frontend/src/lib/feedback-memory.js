const STORAGE_KEY = "warisan.feedback-memory.v1";
const MAX_RECORDS = 50;

function clean(value, maxLength) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function tokens(value) {
  return new Set(clean(value, 2000).toLocaleLowerCase("ms").match(/[\p{L}\p{N}]{3,}/gu) || []);
}

function similarity(left, right) {
  const a = tokens(left);
  const b = tokens(right);
  if (!a.size || !b.size) return 0;
  let shared = 0;
  for (const token of a) if (b.has(token)) shared += 1;
  return shared / Math.max(1, Math.min(a.size, b.size));
}

export function loadFeedbackMemory(storage = window.localStorage) {
  try {
    const parsed = JSON.parse(storage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) =>
      item && ["helpful", "unhelpful"].includes(item.rating) && item.question && item.answer,
    ).slice(0, MAX_RECORDS);
  } catch {
    return [];
  }
}

export function rememberFeedback(entry, storage = window.localStorage) {
  const record = {
    id: clean(entry.messageId || crypto.randomUUID(), 100),
    question: clean(entry.question, 2000),
    answer: clean(entry.answer, 4000),
    rating: entry.rating === "unhelpful" ? "unhelpful" : "helpful",
    correction: clean(entry.correction, 2000),
    createdAt: new Date().toISOString(),
  };
  if (!record.question || !record.answer) return false;
  try {
    const current = loadFeedbackMemory(storage).filter((item) => item.id !== record.id);
    storage.setItem(STORAGE_KEY, JSON.stringify([record, ...current].slice(0, MAX_RECORDS)));
    return true;
  } catch {
    return false;
  }
}

export function relevantFeedback(question, limit = 4, storage = window.localStorage) {
  return loadFeedbackMemory(storage)
    .map((item) => ({ ...item, relevance: similarity(question, item.question) }))
    .filter((item) => item.relevance >= 0.35)
    .sort((a, b) => b.relevance - a.relevance)
    .slice(0, limit)
    .map(({ relevance: _relevance, createdAt: _createdAt, id: _id, ...item }) => item);
}

