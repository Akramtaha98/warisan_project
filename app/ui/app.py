# Run with:
# streamlit run ui/app.py
# streamlit cache clear
import csv
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from phase5_generation import answer_question
except Exception as exc:
    answer_question = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


FEEDBACK_PATH = ROOT_DIR / "data_eval" / "user_feedback.csv"
FEEDBACK_FIELDS = [
    "timestamp",
    "question",
    "answer",
    "rating",
    "feedback_reason",
    "comment",
    "top_score",
    "used_hyde",
    "expanded",
]


SYSTEM_INFO = {
    "Model Bahasa": "Gemma 3 4B",
    "Embedding": "BGE-M3",
    "Reranker": "BGE-Reranker-v2-m3",
    "Vector DB": "ChromaDB",
    "Collection": "dbp_khidmatnasihat_clean_atomic",
    "Jumlah Rekod": "33,320",
}


def init_session_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("feedback_status", {})
    st.session_state.setdefault("feedback_pending", None)


def append_feedback(row: Dict[str, Any]) -> None:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_exists = FEEDBACK_PATH.exists()

    with FEEDBACK_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FEEDBACK_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def log_feedback(message: Dict[str, Any], rating: str, reason: str = "", comment: str = "") -> None:
    debug = message.get("debug", {}) or {}
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": message.get("question", ""),
        "answer": message.get("content", ""),
        "rating": rating,
        "feedback_reason": reason,
        "comment": comment,
        "top_score": debug.get("top_score"),
        "used_hyde": debug.get("used_hyde"),
        "expanded": debug.get("expanded"),
    }
    append_feedback(row)


def format_optional(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}" if value == value else "N/A"
    return str(value)


def format_bool(value: Any) -> str:
    if value is True:
        return "Ya"
    if value is False:
        return "Tidak"
    return "N/A"


def inject_css() -> None:
    st.markdown(
        """
        <style>
            :root {
                --bg-main: #0b1020;
                --bg-panel: rgba(17, 24, 39, 0.78);
                --bg-panel-solid: #111827;
                --border-soft: rgba(148, 163, 184, 0.20);
                --text-main: #f1f5f9;
                --text-muted: #c3cbd9;
                --accent: #a78bfa;
                --accent-2: #22d3ee;
                --success: #34d399;
                --danger: #fb7185;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(124, 58, 237, 0.22), transparent 32rem),
                    radial-gradient(circle at top right, rgba(34, 211, 238, 0.14), transparent 30rem),
                    linear-gradient(135deg, #060913 0%, #0b1020 48%, #111827 100%);
                color: var(--text-main);
            }

            .block-container {
                max-width: 1120px;
                padding-top: 2rem;
                padding-bottom: 6rem;
            }

            section[data-testid="stSidebar"] {
                background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(17, 24, 39, 0.96));
                border-right: 1px solid var(--border-soft);
            }

            section[data-testid="stSidebar"] * {
                color: var(--text-main);
            }

            div[data-testid="stSidebarUserContent"] {
                padding-top: 1.5rem;
            }

            section[data-testid="stSidebar"] hr {
                border-color: rgba(148, 163, 184, 0.16);
                margin: 1rem 0;
            }

            section[data-testid="stSidebar"] [data-testid="column"] {
                padding: 0.1rem 0;
            }

            section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
                color: #94a3b8;
                font-size: 0.82rem;
            }

            .hero-card {
                position: relative;
                overflow: hidden;
                padding: 2rem;
                border: 1px solid rgba(167, 139, 250, 0.30);
                border-radius: 28px;
                background:
                    linear-gradient(135deg, rgba(124, 58, 237, 0.30), rgba(15, 23, 42, 0.86) 48%, rgba(8, 145, 178, 0.16));
                box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
                margin-bottom: 1.3rem;
            }

            .hero-card::after {
                content: "";
                position: absolute;
                width: 220px;
                height: 220px;
                right: -70px;
                top: -80px;
                border-radius: 999px;
                background: rgba(34, 211, 238, 0.16);
                filter: blur(2px);
            }

            .eyebrow {
                display: inline-flex;
                align-items: center;
                gap: 0.45rem;
                padding: 0.38rem 0.72rem;
                border-radius: 999px;
                border: 1px solid rgba(255, 255, 255, 0.14);
                background: rgba(255, 255, 255, 0.07);
                color: #dbeafe;
                font-size: 0.82rem;
                font-weight: 650;
                letter-spacing: 0.02em;
                margin-bottom: 1rem;
            }

            .hero-title {
                margin: 0;
                color: white;
                font-size: clamp(2rem, 5vw, 3.2rem);
                line-height: 1.05;
                font-weight: 800;
                letter-spacing: -0.04em;
            }

            .hero-subtitle {
                max-width: 760px;
                margin: 1rem 0 1.2rem 0;
                color: #cbd5e1;
                font-size: 1.02rem;
                line-height: 1.7;
            }

            .badge-row {
                display: flex;
                flex-wrap: wrap;
                gap: 0.55rem;
            }

            .badge {
                padding: 0.48rem 0.75rem;
                border-radius: 999px;
                background: rgba(15, 23, 42, 0.64);
                border: 1px solid rgba(148, 163, 184, 0.22);
                color: #e2e8f0;
                font-size: 0.84rem;
                font-weight: 600;
            }

            .section-card {
                padding: 1.15rem;
                border-radius: 22px;
                background: var(--bg-panel);
                border: 1px solid var(--border-soft);
                box-shadow: 0 18px 48px rgba(0, 0, 0, 0.18);
                margin-bottom: 1rem;
            }

            .sidebar-title {
                font-size: 1.08rem;
                font-weight: 800;
                margin-bottom: 0.8rem;
                color: white;
            }

            .info-row {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 0.8rem;
                padding: 0.58rem 0;
                border-bottom: 1px solid rgba(148, 163, 184, 0.14);
            }

            .info-row:last-child {
                border-bottom: 0;
            }

            .info-label {
                color: #94a3b8;
                font-size: 0.83rem;
            }

            .info-value {
                color: #f8fafc;
                font-size: 0.83rem;
                font-weight: 700;
                text-align: right;
                overflow-wrap: anywhere;
            }

            .welcome-card {
                padding: 1.2rem 1.3rem;
                border-radius: 22px;
                background: rgba(15, 23, 42, 0.70);
                border: 1px solid rgba(148, 163, 184, 0.18);
                margin: 1rem 0 1.25rem 0;
            }

            .welcome-card h3 {
                margin-top: 0;
                color: white;
            }

            .welcome-card p {
                color: #cbd5e1;
                line-height: 1.7;
                margin-bottom: 0;
            }

            div[data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"],
            div[data-testid="stChatMessage"] [data-testid="stChatMessageAvatarAssistant"] {
                background: linear-gradient(135deg, rgba(167, 139, 250, 0.35), rgba(34, 211, 238, 0.20));
                border: 1px solid rgba(148, 163, 184, 0.22);
            }

            div[data-testid="stChatMessage"] {
                border-radius: 22px;
                border: 1px solid rgba(148, 163, 184, 0.16);
                background: rgba(15, 23, 42, 0.58);
                box-shadow: 0 16px 40px rgba(0, 0, 0, 0.16);
                padding: 0.75rem;
                margin-bottom: 0.75rem;
            }

            /* These had no colour at all, so they inherited Streamlit's default
               text colour instead of the dark-theme one. */
            div[data-testid="stChatMessage"],
            div[data-testid="stChatMessage"] p,
            div[data-testid="stChatMessage"] li,
            div[data-testid="stChatMessage"] span,
            div[data-testid="stChatMessage"] strong {
                color: var(--text-main);
            }

            div[data-testid="stChatMessage"] p,
            div[data-testid="stChatMessage"] li {
                line-height: 1.72;
                font-size: 1rem;
            }

            div[data-testid="stChatMessage"] strong {
                font-weight: 700;
                color: #ffffff;
            }

            .feedback-panel {
                margin: 0.25rem 0 1.3rem 3rem;
                padding: 0.85rem 1rem;
                border-radius: 18px;
                background: rgba(2, 6, 23, 0.35);
                border: 1px solid rgba(148, 163, 184, 0.16);
            }

            /* Only the sidebar variant was styled before, so main-area captions
               such as "Sahkan jawapan ini:" stayed dim and hard to read. */
            .block-container [data-testid="stCaptionContainer"] p {
                color: var(--text-muted);
                font-size: 0.88rem;
            }

            .feedback-title {
                color: var(--text-muted);
                font-size: 0.9rem;
                margin-bottom: 0.55rem;
            }

            div.stButton > button {
                min-height: 2.35rem;
                padding: 0.35rem 0.85rem;
                border-radius: 999px;
                border: 1px solid rgba(167, 139, 250, 0.35);
                background: rgba(30, 41, 59, 0.70);
                color: #f8fafc;
                font-weight: 700;
                transition: all 0.15s ease-in-out;
            }

            div.stButton > button:hover {
                border-color: rgba(34, 211, 238, 0.65);
                transform: translateY(-1px);
                box-shadow: 0 12px 28px rgba(34, 211, 238, 0.10);
            }

            div[data-testid="stMetric"] {
                padding: 0.85rem;
                border-radius: 18px;
                background: rgba(15, 23, 42, 0.72);
                border: 1px solid rgba(148, 163, 184, 0.18);
            }

            div[data-testid="stExpander"] {
                border-radius: 18px;
                border: 1px solid rgba(148, 163, 184, 0.18);
                background: rgba(15, 23, 42, 0.55);
                overflow: hidden;
            }

            .footer-note {
                margin-top: 2rem;
                padding: 1rem;
                text-align: center;
                color: var(--text-muted);
                font-size: 0.85rem;
                border-top: 1px solid rgba(148, 163, 184, 0.14);
            }

            /* The bottom bar kept Streamlit's light chrome, which read as a white
               slab under the dark gradient. Make it part of the page instead. */
            div[data-testid="stBottom"],
            div[data-testid="stBottomBlockContainer"] {
                background: transparent !important;
            }

            div[data-testid="stBottom"] > div {
                background: linear-gradient(180deg, rgba(11, 16, 32, 0), rgba(11, 16, 32, 0.92) 38%);
                backdrop-filter: blur(6px);
            }

            .stChatInput {
                background: rgba(15, 23, 42, 0.92) !important;
                border: 1px solid rgba(167, 139, 250, 0.32) !important;
                border-radius: 999px !important;
                box-shadow: 0 12px 34px rgba(0, 0, 0, 0.34);
            }

            .stChatInput:focus-within {
                border-color: rgba(34, 211, 238, 0.65) !important;
            }

            .stChatInput textarea {
                border-radius: 999px !important;
                background: transparent !important;
                color: var(--text-main) !important;
            }

            .stChatInput textarea::placeholder {
                color: #93a0b4 !important;
                opacity: 1;
            }

            .stChatInput button {
                color: var(--accent) !important;
            }

            .stChatInput button:hover {
                color: var(--accent-2) !important;
            }

            @media (max-width: 768px) {
                .hero-card {
                    padding: 1.35rem;
                    border-radius: 22px;
                }

                .feedback-panel {
                    margin-left: 0;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="hero-card">
            <div class="eyebrow">▣ Prototaip Akademik Berasaskan LLM & RAG</div>
            <h1 class="hero-title">Sistem Chatbot Khidmat Nasihat Bahasa Melayu</h1>
            <p class="hero-subtitle">
                Sistem ini menjana jawapan berdasarkan konteks daripada pangkalan data
                Khidmat Nasihat Bahasa, Dewan Bahasa dan Pustaka. Antara muka ini direka untuk demonstrasi,
                ujian pengguna, dan semakan teknikal projek tesis.
            </p>
            <div class="badge-row">
                <span class="badge">Dense Retrieval</span>
                <span class="badge">Reranking</span>
                <span class="badge">Selective HyDE</span>
                <span class="badge">Context Validation</span>
                <span class="badge">Local LLM</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_welcome() -> None:
    if st.session_state.messages:
        return

    st.markdown(
        """
        <div class="welcome-card">
            <h3>Selamat datang</h3>
            <p>
                Masukkan soalan berkaitan Khidmat Nasihat Bahasa Melayu di ruangan bawah.
                Sistem akan mendapatkan konteks berkaitan terlebih dahulu sebelum menjana jawapan.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> bool:
    """Render sidebar using native Streamlit elements.

    This avoids raw HTML being printed in the sidebar on some Streamlit versions
    while keeping the improved dark theme from the CSS above.
    """
    with st.sidebar:
        st.markdown("### Maklumat Sistem")

        for label, value in SYSTEM_INFO.items():
            left_col, right_col = st.columns([1.1, 1.35])
            left_col.caption(label)
            right_col.markdown(f"**{value}**")

        st.divider()
        st.markdown("### Kawalan")

        if st.button("Bersihkan Perbualan", use_container_width=True):
            st.session_state.messages = []
            st.session_state.feedback_status = {}
            st.session_state.feedback_pending = None
            st.rerun()

        show_tech = st.checkbox("Paparkan Maklumat Teknikal", value=False)

        st.divider()
        st.markdown("### Nota")
        st.caption(
            "Maklumat teknikal sesuai digunakan semasa ujian, pembentangan sistem, "
            "dan semakan keputusan retrieval."
        )

    return show_tech


def render_feedback(idx: int, message: Dict[str, Any]) -> None:
    """Render feedback controls using native Streamlit layout.

    Keeping this native prevents layout issues caused by opening an HTML div,
    inserting Streamlit widgets, and then closing the div later.
    """
    feedback_status = st.session_state.feedback_status.get(idx)

    st.caption("Sahkan jawapan ini:")
    col_positive, col_negative, col_status = st.columns([0.85, 0.95, 4.2], gap="small")

    if col_positive.button("✅ Sah", key=f"fb_up_{idx}", disabled=feedback_status is not None, use_container_width=True):
        log_feedback(message, rating="positive")
        st.session_state.feedback_status[idx] = "positive"
        st.success("Terima kasih atas maklum balas anda.")

    if col_negative.button("❌ Tidak Sah", key=f"fb_down_{idx}", disabled=feedback_status is not None, use_container_width=True):
        st.session_state.feedback_pending = idx

    if feedback_status == "positive":
        col_status.success("Jawapan telah disahkan.")
    elif feedback_status == "negative":
        col_status.warning("Jawapan telah ditanda tidak sah.")

    if st.session_state.feedback_pending == idx and feedback_status is None:
        with st.form(key=f"fb_form_{idx}"):
            reason = st.selectbox(
                "Mengapa jawapan ini tidak sah?",
                [
                    "Jawapan tidak tepat",
                    "Jawapan tidak lengkap",
                    "Jawapan tidak menjawab soalan",
                    "Maklumat tidak mencukupi",
                    "Lain-lain",
                ],
            )
            comment = st.text_area("Komen tambahan")
            submitted = st.form_submit_button("Hantar Maklum Balas")

        if submitted:
            log_feedback(message, rating="negative", reason=reason, comment=comment)
            st.session_state.feedback_status[idx] = "negative"
            st.session_state.feedback_pending = None
            st.success("Terima kasih atas maklum balas anda.")


def render_technical_info(message: Dict[str, Any]) -> None:
    debug = message.get("debug", {}) or {}
    contexts = message.get("contexts") or []

    with st.expander("Maklumat Teknikal"):
        if debug.get("error"):
            st.error(f"error: {debug.get('error')}")
        if debug.get("error_trace"):
            st.code(debug.get("error_trace"), language="text")

        metric_1, metric_2, metric_3, metric_4 = st.columns(4)
        metric_1.metric("Top Score", format_optional(debug.get("top_score")))
        metric_2.metric("HyDE", format_bool(debug.get("used_hyde")))
        metric_3.metric("Expanded", format_bool(debug.get("expanded")))
        metric_4.metric("Konteks", str(len(contexts)))

        if contexts:
            st.markdown("#### Konteks Dicapai")
            for ctx_idx, ctx in enumerate(contexts, start=1):
                preview = (ctx or "").strip().replace("\n", " ")
                preview = preview[:350] + ("..." if len(preview) > 350 else "")
                st.markdown(f"**[{ctx_idx}]** {preview}")


def render_messages(show_tech: bool) -> None:
    for idx, message in enumerate(st.session_state.messages):
        avatar = "🧑‍🎓" if message["role"] == "user" else "📚"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

        if message["role"] != "assistant":
            continue

        render_feedback(idx, message)

        if show_tech:
            render_technical_info(message)


def generate_answer(prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Sedang menjana jawapan berdasarkan konteks dokumen..."):
        try:
            result = answer_question(prompt)
            answer = result.get("answer", "")
            debug = {
                "top_score": result.get("top_score"),
                "used_hyde": result.get("used_hyde"),
                "expanded": result.get("expanded"),
            }
            contexts = result.get("retrieved_contexts") or []
        except Exception as exc:
            st.error(
                "Tidak dapat berhubung dengan LM Studio atau model belum dimuatkan. "
                "Sila pastikan LM Studio sedang berjalan dan model telah dipilih."
            )
            answer = "Maaf, terdapat ralat semasa menjana jawapan. Sila cuba lagi."
            debug = {
                "top_score": None,
                "used_hyde": None,
                "expanded": None,
                "error": str(exc),
                "error_trace": traceback.format_exc(),
            }
            contexts = []

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "question": prompt,
            "debug": debug,
            "contexts": contexts,
        }
    )
    st.rerun()


st.set_page_config(
    page_title="Sistem Chatbot Khidmat Nasihat Bahasa Melayu",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()
inject_css()
show_tech = render_sidebar()
render_header()

if IMPORT_ERROR is not None:
    st.error("Gagal memuatkan backend. Sila semak konfigurasi projek.")
    st.caption(str(IMPORT_ERROR))
    st.stop()

render_welcome()
render_messages(show_tech)

prompt = st.chat_input("Tanya soalan khidmat nasihat Bahasa Melayu")

if prompt:
    generate_answer(prompt)

st.markdown(
    """
    <div class="footer-note">
        Prototaip chatbot akademik berasaskan LLM & RAG untuk Khidmat Nasihat Bahasa Melayu (Dewan Bahasa dan Pustaka).
    </div>
    """,
    unsafe_allow_html=True,
)
