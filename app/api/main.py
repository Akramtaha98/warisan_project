"""FastAPI application serving the React UI and grounded chatbot endpoints."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Literal, Optional
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .service import append_feedback, build_chat_response


APP_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = APP_DIR / "scripts"
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIST", APP_DIR / "frontend_dist"))
FEEDBACK_PATH = Path(os.getenv("FEEDBACK_PATH", APP_DIR / "data_eval" / "user_feedback.csv"))

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from phase5_generation import answer_question  # noqa: E402


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


class FeedbackRequest(BaseModel):
    message_id: str = Field(max_length=120)
    question: str = Field(max_length=2000)
    answer: str = Field(max_length=6000)
    rating: Literal["helpful", "unhelpful"]
    reason: str = Field(default="", max_length=300)
    comment: str = Field(default="", max_length=2000)
    top_score: Optional[float] = None
    question_type: str = Field(default="general", max_length=80)
    thinking_mode: str = Field(default="direct", max_length=80)


app = FastAPI(
    title="Warisan DBP Chatbot",
    description="Grounded Bahasa Melayu language-advisory API",
    version="2.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.get("/api/health")
def health() -> dict:
    chroma_path = Path(os.getenv("CHROMA_PERSIST_DIR", "/app/data/chroma_db")) / "chroma.sqlite3"
    llm_url = os.getenv("LMSTUDIO_BASE_URL", "http://llm:8080/v1/").rstrip("/") + "/models"
    llm_ready = False
    try:
        with urlopen(llm_url, timeout=2) as response:  # nosec B310 - configured internal endpoint
            llm_ready = response.status == 200
    except (OSError, URLError):
        pass
    ready = chroma_path.is_file() and llm_ready
    return {
        "status": "ready" if ready else "degraded",
        "database_ready": chroma_path.is_file(),
        "model_ready": llm_ready,
        "model": os.getenv("LMSTUDIO_MODEL", "Qwen/Qwen3-8B"),
        "collection": os.getenv(
            "CHROMA_COLLECTION_NAME", "dbp_khidmatnasihat_clean_atomic"
        ),
    }


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict:
    try:
        return await run_in_threadpool(build_chat_response, request.question, answer_question)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Sistem jawapan belum tersedia. Semak model Qwen3 dan pangkalan data.",
        ) from exc


@app.post("/api/feedback", status_code=201)
async def feedback(request: FeedbackRequest) -> dict:
    await run_in_threadpool(append_feedback, FEEDBACK_PATH, request.model_dump())
    return {"status": "saved"}


if (FRONTEND_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str) -> FileResponse:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found.")
    index = FRONTEND_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="Antara muka React belum dibina.")
    return FileResponse(index)
