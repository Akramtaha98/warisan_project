"""Framework-independent service helpers for the chatbot API."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Iterable


MAX_QUESTION_LENGTH = 2000
MAX_FEEDBACK_LENGTH = 2000
FEEDBACK_FIELDS = (
    "timestamp",
    "message_id",
    "question",
    "answer",
    "rating",
    "reason",
    "comment",
    "top_score",
    "question_type",
    "thinking_mode",
)
_FEEDBACK_LOCK = Lock()
_ANSWER_LOCK = Lock()


def normalize_question(value: str) -> str:
    question = " ".join((value or "").split()).strip()
    if len(question) < 2:
        raise ValueError("Sila masukkan soalan yang lengkap.")
    if len(question) > MAX_QUESTION_LENGTH:
        raise ValueError(f"Soalan mesti kurang daripada {MAX_QUESTION_LENGTH} aksara.")
    return question


def _source_previews(contexts: Iterable[str]) -> list[Dict[str, Any]]:
    previews = []
    for index, context in enumerate(contexts, start=1):
        cleaned = " ".join((context or "").split())
        if not cleaned:
            continue
        previews.append(
            {
                "index": index,
                "preview": cleaned[:320] + ("…" if len(cleaned) > 320 else ""),
            }
        )
    return previews


def build_chat_response(
    question: str,
    answerer: Callable[[str], Dict[str, Any]],
) -> Dict[str, Any]:
    normalized = normalize_question(question)
    # BGE models and the local GGUF server are expensive shared resources. Keep
    # one in-process retrieval/generation job active at a time to avoid memory
    # spikes and thread-safety surprises on the lab workstation.
    with _ANSWER_LOCK:
        result = answerer(normalized) or {}
    answer = str(result.get("answer") or "").strip()
    if not answer:
        raise RuntimeError("Model tidak menghasilkan jawapan.")

    debug = result.get("debug") or {}
    contexts = result.get("retrieved_contexts") or []
    return {
        "answer": answer,
        "question": normalized,
        "top_score": result.get("top_score", debug.get("top_score")),
        "used_hyde": bool(result.get("used_hyde", debug.get("used_hyde", False))),
        "expanded": bool(result.get("expanded", debug.get("expanded", False))),
        "question_type": result.get("question_type") or debug.get("question_type") or "general",
        "thinking_mode": result.get("thinking_mode") or debug.get("thinking_mode") or "direct",
        "sources": _source_previews(contexts),
    }


def _safe_csv_cell(value: Any, limit: int = MAX_FEEDBACK_LENGTH) -> str:
    text = str(value or "").replace("\x00", "").strip()[:limit]
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def append_feedback(path: Path, payload: Dict[str, Any]) -> None:
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message_id": _safe_csv_cell(payload.get("message_id"), 120),
        "question": _safe_csv_cell(payload.get("question")),
        "answer": _safe_csv_cell(payload.get("answer"), 6000),
        "rating": _safe_csv_cell(payload.get("rating"), 40),
        "reason": _safe_csv_cell(payload.get("reason"), 300),
        "comment": _safe_csv_cell(payload.get("comment")),
        "top_score": _safe_csv_cell(payload.get("top_score"), 80),
        "question_type": _safe_csv_cell(payload.get("question_type"), 80),
        "thinking_mode": _safe_csv_cell(payload.get("thinking_mode"), 80),
    }
    with _FEEDBACK_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FEEDBACK_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
