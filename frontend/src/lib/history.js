export const HISTORY_STORAGE_KEY = "warisan.chat-history.v1";
export const MAX_SAVED_CONVERSATIONS = 24;

function validMessage(message) {
  return message &&
    typeof message.id === "string" &&
    ["user", "assistant"].includes(message.role) &&
    typeof message.content === "string";
}

function normalizeSession(session) {
  if (!session || typeof session.id !== "string" || !Array.isArray(session.messages)) return null;
  const messages = session.messages.filter(validMessage).slice(-80);
  if (!messages.length) return null;
  return {
    id: session.id,
    title: makeSessionTitle(messages),
    messages,
    createdAt: Number(session.createdAt) || Date.now(),
    updatedAt: Number(session.updatedAt) || Date.now(),
  };
}

export function makeSessionTitle(messages) {
  const firstQuestion = messages.find((message) => message.role === "user")?.content?.trim();
  if (!firstQuestion) return "Perbualan baharu";
  return firstQuestion.length > 46 ? `${firstQuestion.slice(0, 45).trim()}…` : firstQuestion;
}

export function loadChatHistory(storage = globalThis.localStorage) {
  try {
    const parsed = JSON.parse(storage?.getItem(HISTORY_STORAGE_KEY) || "null");
    const sessions = Array.isArray(parsed?.sessions)
      ? parsed.sessions.map(normalizeSession).filter(Boolean).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX_SAVED_CONVERSATIONS)
      : [];
    const requestedActive = typeof parsed?.activeSessionId === "string" ? parsed.activeSessionId : null;
    const activeSessionId = sessions.some((session) => session.id === requestedActive)
      ? requestedActive
      : sessions[0]?.id || null;
    return { sessions, activeSessionId };
  } catch {
    return { sessions: [], activeSessionId: null };
  }
}

export function saveChatHistory(state, storage = globalThis.localStorage) {
  try {
    storage?.setItem(HISTORY_STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

export function updateConversation(state, sessionId, messages, now = Date.now()) {
  const existing = state.sessions.find((session) => session.id === sessionId);
  const updated = {
    id: sessionId,
    title: makeSessionTitle(messages),
    messages: messages.slice(-80),
    createdAt: existing?.createdAt || now,
    updatedAt: now,
  };
  return {
    activeSessionId: sessionId,
    sessions: [updated, ...state.sessions.filter((session) => session.id !== sessionId)].slice(0, MAX_SAVED_CONVERSATIONS),
  };
}

export function removeConversation(state, sessionId) {
  const sessions = state.sessions.filter((session) => session.id !== sessionId);
  return {
    sessions,
    activeSessionId: state.activeSessionId === sessionId ? sessions[0]?.id || null : state.activeSessionId,
  };
}

