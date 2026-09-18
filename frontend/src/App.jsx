import { useEffect, useRef, useState } from "react";
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
  Menu,
  MessageCircleMore,
  Plus,
  RotateCcw,
  SearchCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  X,
  Zap,
} from "lucide-react";
import { askQuestion, getHealth, sendFeedback } from "./lib/api";
import { intentLabels, suggestions } from "./data/suggestions";

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

function Sidebar({ open, onClose, onReset, hasMessages, health }) {
  return (
    <>
      {open && <button className="sidebar-scrim" onClick={onClose} aria-label="Tutup menu" />}
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <div className="sidebar-top">
          <Brand />
          <button className="icon-button sidebar-close" onClick={onClose} aria-label="Tutup menu"><X size={20} /></button>
        </div>

        <button className="new-chat-button" onClick={onReset}>
          <Plus size={18} />
          Perbualan baharu
        </button>

        <div className="sidebar-section">
          <div className="sidebar-label"><History size={14} /> Sesi semasa</div>
          <button className={`history-item ${hasMessages ? "has-content" : ""}`} disabled={!hasMessages} onClick={onClose}>
            <MessageCircleMore size={17} />
            <span>{hasMessages ? "Perbualan bahasa anda" : "Belum ada perbualan"}</span>
          </button>
        </div>

        <div className="sidebar-spacer" />

        <div className="knowledge-card">
          <div className="knowledge-icon"><Database size={18} /></div>
          <div>
            <strong>Sumber dipercayai</strong>
            <p>33,320 rekod Khidmat Nasihat Bahasa DBP</p>
          </div>
        </div>

        <div className="sidebar-footer">
          <StatusPill health={health} />
          <span>Qwen3 · BGE-M3</span>
        </div>
      </aside>
    </>
  );
}

function Welcome({ onSelect }) {
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <div className="welcome-orbit" aria-hidden="true">
        <div className="welcome-emblem"><span>و</span></div>
      </div>
      <div className="welcome-kicker"><Sparkles size={15} /> Bahasa yang tepat, jawapan yang bersumber</div>
      <h1 id="welcome-title">Bahasa mencerminkan<br /><em>jati diri.</em></h1>
      <p className="welcome-copy">
        Tanyakan tentang ejaan, istilah, tatabahasa atau penggunaan Bahasa Melayu.
        Setiap jawapan disemak terhadap sumber Khidmat Nasihat DBP.
      </p>

      <div className="suggestion-grid">
        {suggestions.map(({ icon: Icon, label, prompt }) => (
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

function Composer({ value, onChange, onSubmit, disabled }) {
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
      <p className="composer-note">Jawapan dijana berdasarkan sumber DBP. Sila sahkan maklumat penting.</p>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [health, setHealth] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ status: "degraded" }));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  async function submitQuestion(forcedQuestion, appendUser = true) {
    const prompt = (forcedQuestion ?? question).trim();
    if (prompt.length < 2 || loading) return;
    setQuestion("");
    setError(null);
    setLoading(true);
    if (appendUser) {
      const userMessage = { id: crypto.randomUUID(), role: "user", content: prompt };
      setMessages((current) => [...current, userMessage]);
    }
    try {
      const response = await askQuestion(prompt);
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          question: prompt,
          content: response.answer,
          meta: response,
        },
      ]);
    } catch (requestError) {
      setError({ message: requestError.message, prompt });
    } finally {
      setLoading(false);
    }
  }

  function resetConversation() {
    setMessages([]);
    setQuestion("");
    setError(null);
    setSidebarOpen(false);
  }

  return (
    <div className="app-shell">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onReset={resetConversation}
        hasMessages={messages.length > 0}
        health={health}
      />

      <main className="main-panel">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setSidebarOpen(true)} aria-label="Buka menu"><Menu size={21} /></button>
          <div className="mobile-brand"><Brand /></div>
          <div className="topbar-title">
            <span>Khidmat Nasihat Bahasa</span>
            <small>Jawapan berasaskan sumber DBP</small>
          </div>
          <StatusPill health={health} />
          {messages.length > 0 && <button className="reset-button" onClick={resetConversation}><RotateCcw size={15} /> Mula semula</button>}
        </header>

        <div className={`conversation ${messages.length ? "has-messages" : "is-empty"}`}>
          {messages.length === 0 ? (
            <Welcome onSelect={(prompt) => submitQuestion(prompt)} />
          ) : (
            <div className="message-list">
              {messages.map((message) => <Message key={message.id} message={message} />)}
              {loading && <ThinkingMessage />}
              {error && (
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

        <Composer value={question} onChange={setQuestion} onSubmit={() => submitQuestion()} disabled={loading} />
      </main>
    </div>
  );
}
