import assert from "node:assert/strict";
import test from "node:test";
import {
  boundedHistory,
  buildRetrievalQuery,
  records,
  retrieveFixtures,
} from "../_lib/retrieval.js";

test("fixture contains 100 unique and complete Malay QA evaluation records", () => {
  assert.equal(records.length, 100);
  assert.equal(new Set(records.map((record) => record.id)).size, records.length);
  assert.ok(new Set(records.map((record) => record.category)).size >= 30);
  assert.ok(records.filter((record) => record.difficulty === "hard").length >= 12);
  for (const record of records) {
    assert.match(record.id, /^qa-ms-\d{3}$/);
    assert.ok(record.category.length >= 3);
    assert.ok(record.question.length >= 12);
    assert.ok(record.answer.length >= 30);
  }
});

test("retrieval selects relevant Malay QA records", () => {
  assert.equal(retrieveFixtures("Apakah beza ialah dan adalah?").matches[0].id, "qa-ms-001");
  assert.equal(retrieveFixtures("Adakah di sekolah ditulis rapat?").matches[0].id, "qa-ms-004");
  assert.equal(retrieveFixtures("Cara menulis kereta api").matches[0].id, "qa-ms-009");
  assert.equal(retrieveFixtures("Apakah padanan bagi download?").matches[0].id, "qa-ms-080");
  assert.equal(retrieveFixtures("Betulkan para pelajar-pelajar di minta mengulangkaji").matches[0].id, "qa-ms-099");
});

test("short follow-up uses bounded conversation history", () => {
  const history = [
    { role: "user", content: "Apakah perbezaan antara dari dengan daripada?" },
    { role: "assistant", content: "Kedua-duanya ialah kata sendi." },
  ];
  assert.match(buildRetrievalQuery("contoh pula?", history), /dari dengan daripada/);
  assert.equal(retrieveFixtures("contoh pula?", history).matches[0].id, "qa-ms-087");
  assert.equal(boundedHistory([...Array(10)].map((_, index) => ({ role: "user", content: `x${index}` }))).length, 6);
});
