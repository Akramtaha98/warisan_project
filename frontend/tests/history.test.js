import assert from "node:assert/strict";
import test from "node:test";
import {
  HISTORY_STORAGE_KEY,
  MAX_SAVED_CONVERSATIONS,
  loadChatHistory,
  makeSessionTitle,
  removeConversation,
  saveChatHistory,
  updateConversation,
} from "../src/lib/history.js";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

function message(id, role, content) {
  return { id, role, content };
}

test("conversation titles are derived from the first question and safely shortened", () => {
  assert.equal(makeSessionTitle([message("1", "assistant", "Hai")]), "Perbualan baharu");
  assert.equal(makeSessionTitle([message("2", "user", "Apakah fungsi tanda soal?")]), "Apakah fungsi tanda soal?");
  assert.match(makeSessionTitle([message("3", "user", "a".repeat(70))]), /^a{45}…$/);
});

test("history saves, restores, sorts, and ignores malformed records", () => {
  const storage = memoryStorage();
  let state = { sessions: [], activeSessionId: null };
  state = updateConversation(state, "older", [message("1", "user", "Soalan lama")], 10);
  state = updateConversation(state, "newer", [message("2", "user", "Soalan baharu")], 20);
  assert.equal(saveChatHistory(state, storage), true);
  const loaded = loadChatHistory(storage);
  assert.deepEqual(loaded.sessions.map(({ id }) => id), ["newer", "older"]);
  assert.equal(loaded.activeSessionId, "newer");

  const malformed = memoryStorage({ [HISTORY_STORAGE_KEY]: '{"sessions":[{"id":7}]}' });
  assert.deepEqual(loadChatHistory(malformed), { sessions: [], activeSessionId: null });
});

test("history is bounded and deleting the active conversation selects the next one", () => {
  let state = { sessions: [], activeSessionId: null };
  for (let index = 0; index < MAX_SAVED_CONVERSATIONS + 4; index += 1) {
    state = updateConversation(state, `s${index}`, [message(`m${index}`, "user", `Soalan ${index}`)], index + 1);
  }
  assert.equal(state.sessions.length, MAX_SAVED_CONVERSATIONS);
  assert.equal(state.sessions[0].id, `s${MAX_SAVED_CONVERSATIONS + 3}`);
  const removed = removeConversation(state, state.activeSessionId);
  assert.equal(removed.sessions.length, MAX_SAVED_CONVERSATIONS - 1);
  assert.equal(removed.activeSessionId, removed.sessions[0].id);
});

test("unavailable browser storage fails without breaking the app", () => {
  const broken = {
    getItem() { throw new Error("blocked"); },
    setItem() { throw new Error("blocked"); },
  };
  assert.deepEqual(loadChatHistory(broken), { sessions: [], activeSessionId: null });
  assert.equal(saveChatHistory({ sessions: [], activeSessionId: null }, broken), false);
});
