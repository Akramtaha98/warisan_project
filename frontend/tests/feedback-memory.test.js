import assert from "node:assert/strict";
import test from "node:test";
import { loadFeedbackMemory, relevantFeedback, rememberFeedback } from "../src/lib/feedback-memory.js";

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

test("feedback memory saves helpful answers and user corrections", () => {
  const storage = memoryStorage();
  assert.equal(rememberFeedback({
    messageId: "liked-1",
    question: "Apakah fungsi tanda soal?",
    answer: "Tanda soal mengakhiri ayat tanya.",
    rating: "helpful",
  }, storage), true);
  assert.equal(rememberFeedback({
    messageId: "fixed-1",
    question: "Apakah fungsi koma?",
    answer: "Jawapan kurang tepat.",
    rating: "unhelpful",
    correction: "Koma menandakan jeda dalam ayat.",
  }, storage), true);
  const saved = loadFeedbackMemory(storage);
  assert.equal(saved.length, 2);
  assert.equal(saved[0].correction, "Koma menandakan jeda dalam ayat.");
});

test("only related feedback is supplied to a new question", () => {
  const storage = memoryStorage();
  rememberFeedback({
    messageId: "m1",
    question: "Apakah fungsi tanda soal dalam ayat?",
    answer: "Jawapan lama.",
    rating: "unhelpful",
    correction: "Tanda soal hadir pada akhir ayat tanya langsung.",
  }, storage);
  rememberFeedback({
    messageId: "m2",
    question: "Apakah ejaan kerjasama?",
    answer: "Kerjasama dieja rapat.",
    rating: "helpful",
  }, storage);
  const matches = relevantFeedback("Jelaskan fungsi tanda soal dalam ayat", 4, storage);
  assert.equal(matches.length, 1);
  assert.equal(matches[0].correction, "Tanda soal hadir pada akhir ayat tanya langsung.");
});

