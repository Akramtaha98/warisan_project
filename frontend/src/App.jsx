import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  ArrowUp,
  BookMarked,
  Check,
  ChevronDown,
  Clipboard,
  Database,
  HelpCircle,
  History,
  Gauge,
  Menu,
  MessageCircleMore,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RotateCcw,
  Search,
  SearchCheck,
  Sparkles,
  Sun,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { askQuestion, getHealth, sendFeedback } from "./lib/api";
import { demoSuggestions, intentLabels, suggestions } from "./data/suggestions";
import { loadChatHistory, removeConversation, saveChatHistory, updateConversation } from "./lib/history";
import { applyTheme, resolveTheme, saveTheme } from "./lib/theme";

const MAX_QUESTION_LENGTH = 2000;

function Brand() {
  return (
    <div className="brand" aria-label="Warisan DBP">
      <div className="brand-mark"><BookMarked size={21} strokeWidth={1.8} /></div>
      <div>
        <div className="brand-name">Warisan</div>
        <div className="brand-caption">Pembantu Bahasa Melayu</div>
      </div>
    </div>
  );
}

function StatusPill({ health }) {
  const ready = health?.status === "ready";
  return (
    <div className={`status-pill ${ready ? "is-ready" : "is-waiting"}`} title={ready ? "Semua sistem tersedia" : "Sistem sedang disemak"}>
      <span className="status-dot" />
      <span>{ready ? "Sedia" : "Mod terhad"}</span>
    </div>
  );
}

function formatHistoryTime(timestamp) {
  const date = new Date(timestamp);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString("ms-MY", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("ms-MY", { day: "numeric", month: "short" });
}

function Sidebar({ open, collapsed, onClose, onToggleCollapse, onNewChat, sessions, activeSessionId, onSelectSession, onDeleteSession, health }) {
  const demo = health?.mode === "vercel-demo";
  const [historyQuery, setHistoryQuery] = useState("");
  const visibleSessions = useMemo(() => {
    const query = historyQuery.trim().toLocaleLowerCase("ms");
    return query ? sessions.filter((session) => session.title.toLocaleLowerCase("ms").includes(query)) : sessions;
  }, [historyQuery, sessions]);
  return (
    <>
      {open && <button className="sidebar-scrim" onClick={onClose} aria-label="Tutup menu" />}
      <aside className={`sidebar ${open ? "is-open" : ""} ${collapsed ? "is-collapsed" : ""}`}>
        <div className="sidebar-top">
          <Brand />
          <button
            className="icon-button sidebar-collapse"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Kembangkan panel sisi" : "Runtuhkan panel sisi"}
            title={collapsed ? "Kembangkan panel" : "Runtuhkan panel"}
          >
            {collapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}
          </button>
          <button className="icon-button sidebar-close" onClick={onClose} aria-label="Tutup menu"><X size={20} /></button>
        </div>

        <button className="new-chat-button" onClick={onNewChat} aria-label="Perbualan baharu" title={collapsed ? "Perbualan baharu" : undefined}>
          <Plus size={18} />
          <span>Perbualan baharu</span>
        </button>

        <div className="sidebar-section history-section">
          <div className="sidebar-label">
            <History size={14} />
            <span className="sidebar-label-text">Sejarah perbualan</span>
            <span className="history-count">{sessions.length}</span>
          </div>
          {sessions.length > 3 && (
            <label className="history-search">
              <Search size={14} />
              <input value={historyQuery} onChange={(event) => setHistoryQuery(event.target.value)} placeholder="Cari perbualan" />
            </label>
          )}
          <div className="history-list">
            {visibleSessions.map((session) => (
              <div className={`history-item ${session.id === activeSessionId ? "is-active" : ""}`} key={session.id}>
                <button className="history-main" onClick={() => onSelectSession(session.id)}>
                  <span className="history-icon"><MessageCircleMore size={16} /></span>
                  <span className="history-copy">
                    <strong>{session.title}</strong>
                    <small>{formatHistoryTime(session.updatedAt)} · {session.messages.length} mesej</small>
                  </span>
                </button>
                <button className="history-delete" onClick={() => onDeleteSession(session.id)} aria-label={`Padam ${session.title}`} title="Padam perbualan">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            {!visibleSessions.length && (
              <div className="history-empty">
                <MessageCircleMore size={18} />
                <span>{sessions.length ? "Tiada padanan ditemui" : "Perbualan anda akan muncul di sini"}</span>
              </div>
            )}
          </div>
        </div>

        <div className="knowledge-card">
          <div className="knowledge-icon"><Database size={18} /></div>
          <div>
            <strong>{demo ? "Dataset demonstrasi" : "Sumber dipercayai"}</strong>
            <p>{demo ? `${health?.records || 100} QA Bahasa Melayu sintetik` : "33,320 rekod Khidmat Nasihat Bahasa DBP"}</p>
          </div>
        </div>

        <div className="sidebar-footer">
          <StatusPill health={health} />
          <span>{demo ? "Qwen3 · Vercel AI" : "Qwen3 · BGE-M3"}</span>
        </div>
      </aside>
    </>
  );
}

function Welcome({ onSelect, demo }) {
  const visibleSuggestions = demo ? demoSuggestions : suggestions;
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <div className="welcome-orbit" aria-hidden="true">
        <div className="welcome-emblem"><span>و</span></div>
      </div>
      <div className="welcome-kicker"><Sparkles size={15} /> Bahasa yang tepat, jawapan yang bersumber</div>
      <h1 id="welcome-title">Bahasa mencerminkan<br /><em>jati diri.</em></h1>
      <p className="welcome-copy">
        {demo
          ? "Uji ejaan, tatabahasa dan penggunaan Bahasa Melayu dengan dataset sintetik yang dinilai oleh Qwen3."
          : "Tanyakan tentang ejaan, istilah, tatabahasa atau penggunaan Bahasa Melayu. Setiap jawapan disemak terhadap sumber Khidmat Nasihat DBP."}
      </p>

      <div className="suggestion-grid">
        {visibleSuggestions.map(({ icon: Icon, label, prompt }) => (
          <button className="suggestion-card" key={label} onClick={() => onSelect(prompt)}>
            <span className="suggestion-icon"><Icon size={19} /></span>
            <span>
              <strong>{label}</strong>
              <small>{prompt}</small>
            </span>
            <ArrowUp className="suggestion-arrow" size={17} />
          </button>
        ))}
      </div>
    </section>
  );
}

function SourceList({ sources }) {
  const [open, setOpen] = useState(false);
  if (!sources?.length) return null;
  return (
    <div className={`sources ${open ? "is-open" : ""}`}>
      <button className="sources-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span><SearchCheck size={16} /> {sources.length} petikan rujukan</span>
        <ChevronDown size={16} />
      </button>
      {open && (
        <div className="source-list">
          {sources.map((source) => (
            <div className="source-item" key={source.index}>
              <span>{source.index}</span>
              <p>{source.preview}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Feedback({ message }) {
  const [rating, setRating] = useState(null);
  const [copied, setCopied] = useState(false);

  async function rate(value) {
    if (rating) return;
    setRating(value);
    try {
      await sendFeedback({
        message_id: message.id,
        question: message.question,
        answer: message.content,
        rating: value,
        top_score: message.meta?.topScore,
        question_type: message.meta?.questionType,
        thinking_mode: message.meta?.thinkingMode,
      });
    } catch {
      setRating(null);
    }
  }

  async function copyAnswer() {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  return (
    <div className="message-actions">
      <button onClick={copyAnswer} aria-label="Salin jawapan" title="Salin jawapan">
        {copied ? <Check size={15} /> : <Clipboard size={15} />}
      </button>
      <span className="action-divider" />
      <span className="action-label">Berguna?</span>
      <button className={rating === "helpful" ? "is-active" : ""} onClick={() => rate("helpful")} aria-label="Jawapan berguna"><ThumbsUp size={15} /></button>
      <button className={rating === "unhelpful" ? "is-active" : ""} onClick={() => rate("unhelpful")} aria-label="Jawapan tidak berguna"><ThumbsDown size={15} /></button>
    </div>
  );
}

function Message({ message }) {
  const assistant = message.role === "assistant";
  const quality = message.meta?.qualityBreakdown;
  const qualityTitle = quality
    ? `Asas fakta ${quality.grounding} · Relevan ${quality.relevance} · Lengkap ${quality.completeness} · Bahasa ${quality.language}`
    : "";
  return (
    <article className={`message-row ${assistant ? "assistant" : "user"}`}>
      {assistant && <div className="assistant-avatar"><Sparkles size={17} /></div>}
      <div className="message-column">
        <div className="message-author">{assistant ? "Warisan" : "Anda"}</div>
        <div className="message-bubble">
          {assistant ? <ReactMarkdown>{message.content}</ReactMarkdown> : <p>{message.content}</p>}
        </div>
        {assistant && message.meta && (
          <>
            <div className="answer-meta">
              <span><BookMarked size={14} /> {intentLabels[message.meta.questionType] || intentLabels.general}</span>
              <span className={message.meta.thinkingMode === "thinking" ? "reasoning-badge" : "direct-badge"}>
                {message.meta.thinkingMode === "thinking" ? <Sparkles size={13} /> : <Zap size={13} />}
                {message.meta.thinkingMode === "thinking" ? "Penaakulan mendalam" : "Jawapan langsung"}
              </span>
              {message.meta.topScore !== null && <span>Skor {message.meta.topScore.toFixed(2)}</span>}
              {message.meta.qualityScore !== null && (
                <span className="quality-badge" title={`${message.meta.qualityLabel}. ${qualityTitle}. ${message.meta.evaluationNote}`}>
                  <Gauge size={13} /> Kualiti Qwen3 {message.meta.qualityScore}/100
                </span>
              )}
            </div>
            <SourceList sources={message.meta.sources} />
            <Feedback message={message} />
          </>
        )}
      </div>
    </article>
  );
}

function ThinkingMessage() {
  return (
    <article className="message-row assistant" aria-live="polite">
      <div className="assistant-avatar is-thinking"><Sparkles size={17} /></div>
      <div className="message-column">
        <div className="message-author">Warisan</div>
        <div className="thinking-card">
          <span /><span /><span />
          <p>Mencari dan menilai sumber DBP…</p>
        </div>
      </div>
    </article>
  );
}

function Composer({ value, onChange, onSubmit, disabled, demo }) {
  const textarea = useRef(null);
  useEffect(() => {
    const node = textarea.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, 148)}px`;
  }, [value]);

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className="composer-wrap">
      <div className={`composer ${disabled ? "is-disabled" : ""}`}>
        <textarea
          ref={textarea}
          value={value}
          onChange={(event) => onChange(event.target.value.slice(0, MAX_QUESTION_LENGTH))}
          onKeyDown={handleKeyDown}
          placeholder="Tanyakan sesuatu tentang Bahasa Melayu…"
          rows={1}
          disabled={disabled}
          aria-label="Soalan Bahasa Melayu"
        />
        <div className="composer-bottom">
          <span>{value.length ? `${value.length}/${MAX_QUESTION_LENGTH}` : "Enter untuk hantar · Shift + Enter untuk baris baharu"}</span>
          <button onClick={onSubmit} disabled={disabled || value.trim().length < 2} aria-label="Hantar soalan">
            <ArrowUp size={19} strokeWidth={2.4} />
          </button>
        </div>
      </div>
      <p className="composer-note">{demo ? "Demo menggunakan data sintetik. Skor Qwen3 bukan pengesahan rasmi." : "Jawapan dijana berdasarkan sumber DBP. Sila sahkan maklumat penting."}</p>
    </div>
  );
}

export default function App() {
  const [chatState, setChatState] = useState(() => loadChatHistory());
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [pendingSessionId, setPendingSessionId] = useState(null);
  const [error, setError] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem("warisan.sidebar-collapsed.v1") === "true";
    } catch {
      return false;
    }
  });
  const [health, setHealth] = useState(null);
  const [theme, setTheme] = useState(() => resolveTheme());
  const bottomRef = useRef(null);
  const activeSession = chatState.sessions.find((session) => session.id === chatState.activeSessionId);
  const messages = activeSession?.messages || [];

  useEffect(() => {
    saveChatHistory(chatState);
  }, [chatState]);

  useLayoutEffect(() => {
    applyTheme(theme);
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    try {
      window.localStorage.setItem("warisan.sidebar-collapsed.v1", String(sidebarCollapsed));
    } catch {
      // The layout still works when browser storage is unavailable.
    }
  }, [sidebarCollapsed]);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ status: "degraded" }));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading, chatState.activeSessionId]);

  async function submitQuestion(forcedQuestion, appendUser = true) {
    const prompt = (forcedQuestion ?? question).trim();
    if (prompt.length < 2 || loading) return;
    const sessionId = chatState.activeSessionId || crypto.randomUUID();
    const startingMessages = activeSession?.messages || [];
    const nextMessages = appendUser
      ? [...startingMessages, { id: crypto.randomUUID(), role: "user", content: prompt }]
      : startingMessages;
    setQuestion("");
    setError(null);
    setLoading(true);
    setPendingSessionId(sessionId);
    setChatState((current) => updateConversation(current, sessionId, nextMessages));
    try {
      const history = startingMessages.slice(-6).map(({ role, content }) => ({ role, content }));
      const response = await askQuestion(prompt, history);
      setChatState((current) => {
        const target = current.sessions.find((session) => session.id === sessionId);
        const targetMessages = target?.messages || nextMessages;
        return updateConversation(current, sessionId, [...targetMessages, {
          id: crypto.randomUUID(),
          role: "assistant",
          question: prompt,
          content: response.answer,
          meta: response,
        }]);
      });
    } catch (requestError) {
      setError({ message: requestError.message, prompt, sessionId });
    } finally {
      setLoading(false);
      setPendingSessionId(null);
    }
  }

  function startNewConversation() {
    setChatState((current) => ({ ...current, activeSessionId: null }));
    setQuestion("");
    setError(null);
    setSidebarOpen(false);
  }

  function selectConversation(sessionId) {
    setChatState((current) => ({ ...current, activeSessionId: sessionId }));
    setError(null);
    setSidebarOpen(false);
  }

  function deleteConversation(sessionId) {
    setChatState((current) => removeConversation(current, sessionId));
    if (error?.sessionId === sessionId) setError(null);
  }

  return (
    <div className="app-shell">
      <Sidebar
        open={sidebarOpen}
        collapsed={sidebarCollapsed}
        onClose={() => setSidebarOpen(false)}
        onToggleCollapse={() => setSidebarCollapsed((current) => !current)}
        onNewChat={startNewConversation}
        sessions={chatState.sessions}
        activeSessionId={chatState.activeSessionId}
        onSelectSession={selectConversation}
        onDeleteSession={deleteConversation}
        health={health}
      />

      <main className={`main-panel ${sidebarCollapsed ? "is-sidebar-collapsed" : ""}`}>
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setSidebarOpen(true)} aria-label="Buka menu"><Menu size={21} /></button>
          <div className="mobile-brand"><Brand /></div>
          <div className="topbar-title">
            <span>{activeSession?.title || "Khidmat Nasihat Bahasa"}</span>
            <small>{health?.mode === "vercel-demo" ? "Demo QA Melayu · dinilai Qwen3" : "Jawapan berasaskan sumber DBP"}</small>
          </div>
          <StatusPill health={health} />
          <button
            className="icon-button theme-toggle"
            onClick={() => setTheme((current) => current === "dark" ? "light" : "dark")}
            aria-label={theme === "dark" ? "Gunakan mod cerah" : "Gunakan mod gelap"}
            title={theme === "dark" ? "Mod cerah" : "Mod gelap"}
            aria-pressed={theme === "dark"}
          >
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          {messages.length > 0 && <button className="reset-button" onClick={startNewConversation}><RotateCcw size={15} /> Chat baharu</button>}
        </header>

        <div className={`conversation ${messages.length ? "has-messages" : "is-empty"}`}>
          {messages.length === 0 ? (
            <Welcome onSelect={(prompt) => submitQuestion(prompt)} demo={health?.mode === "vercel-demo"} />
          ) : (
            <div className="message-list">
              {messages.map((message) => <Message key={message.id} message={message} />)}
              {loading && pendingSessionId === chatState.activeSessionId && <ThinkingMessage />}
              {error?.sessionId === chatState.activeSessionId && (
                <div className="error-card" role="alert">
                  <HelpCircle size={18} />
                  <div><strong>Jawapan tidak dapat dijana</strong><p>{error.message}</p></div>
                  <button onClick={() => submitQuestion(error.prompt, false)}>Cuba lagi</button>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <Composer value={question} onChange={setQuestion} onSubmit={() => submitQuestion()} disabled={loading} demo={health?.mode === "vercel-demo"} />
      </main>
    </div>
  );
}
