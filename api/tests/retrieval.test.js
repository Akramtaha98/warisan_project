import assert from "node:assert/strict";
import test from "node:test";
import {
  boundedHistory,
  buildRetrievalQuery,
  records,
  retrieveFixtures,
} from "../_lib/retrieval.js";

test("fixture contains the reviewed simple Malay QA dataset", () => {
  assert.equal(records.length, 24);
  assert.equal(new Set(records.map((record) => record.id)).size, records.length);
});

test("retrieval selects relevant Malay QA records", () => {
  assert.equal(retrieveFixtures("Apakah beza ialah dan adalah?").matches[0].id, "qa-ms-001");
  assert.equal(retrieveFixtures("Adakah di sekolah ditulis rapat?").matches[0].id, "qa-ms-004");
  assert.equal(retrieveFixtures("Cara menulis kereta api").matches[0].id, "qa-ms-009");
});

test("short follow-up uses bounded conversation history", () => {
  const history = [
    { role: "user", content: "Apakah perbezaan antara dari dengan daripada?" },
    { role: "assistant", content: "Kedua-duanya ialah kata sendi." },
  ];
  assert.match(buildRetrievalQuery("contoh pula?", history), /dari dengan daripada/);
  assert.equal(retrieveFixtures("contoh pula?", history).matches[0].id, "qa-ms-003");
  assert.equal(boundedHistory([...Array(10)].map((_, index) => ({ role: "user", content: `x${index}` }))).length, 6);
});
