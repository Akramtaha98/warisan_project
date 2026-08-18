"""
phase4_retrieval_rerank.py
Phase 4: Dense Retrieval → Rerank → Filter → Adaptive Expand → HyDE Fallback (LM Studio) → Final Selection

Key points for your setup:
- Chroma collection was created with persisted embedding_function = "default"
  => DO NOT pass embedding_function when getting the collection.
  => Embed query yourself using BGE-M3 and call collection.query(query_embeddings=...)

- HyDE (Gemma 4B via LM Studio) is used conditionally when retrieval is weak.
  This version includes:
  1) Stronger HyDE prompt to force "kata penguat" meaning (tatabahasa) not electronics
  2) Safety validator to discard off-domain HyDE text

Requirements (rag4 env):
  pip install requests chromadb FlagEmbedding transformers==4.44.2 accelerate torch torchvision torchaudio

LM Studio:
- Enable server (OpenAI-compatible)
- Base URL default: http://127.0.0.1:1234/v1
- Ensure cfg.lmstudio_model matches model id in LM Studio
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import re
import sqlite3
import os

import requests
import chromadb
from chromadb.api.models.Collection import Collection

from FlagEmbedding import BGEM3FlagModel, FlagReranker
import sys

# -----------------------------
# Config
# -----------------------------
@dataclass
class RAGConfig:
    # Chroma
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "/app/data/chroma_db")
    collection_name: str = os.getenv("CHROMA_COLLECTION_NAME", "dbp_khidmatnasihat_clean_atomic")

    # Retrieval / Rerank
    final_n: int = 3               # cap only; filter decides actual count
    min_keep_score: float = 0.8   # keep only chunks with rerank_score >= this

    # Adaptive retrieval (expand k when weak)
    k_small: int = 5
    k_large: int = 10
    min_top_score_expand: float = 0.5  # expand retrieval if top rerank score < this

    # HyDE trigger (run HyDE only when still weak after expansion)
    # For real usage keep low (e.g., 0.3–0.7). For testing you can temporarily set higher.
    hyde_trigger_threshold: float = 0.5

    # Embedding settings
    device: str = os.getenv("RAG_DEVICE", "cpu")
    use_fp16: bool = os.getenv("RAG_USE_FP16", "false").lower() in {"1", "true", "yes"}
    embed_max_length: int = 512
    embed_batch_size: int = 16

    # LM Studio (OpenAI-compatible)
    lmstudio_base_url: str = os.getenv("LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1/")
    lmstudio_model: str = os.getenv("LMSTUDIO_MODEL", "google/gemma-3-4b")
    lmstudio_timeout_s: int = int(os.getenv("LMSTUDIO_TIMEOUT_S", "60"))


CFG = RAGConfig()


# -----------------------------
# Init
# -----------------------------
class SQLiteFallbackCollection:
    def __init__(self, db_path: str, collection_name: str):
        self.db_path = db_path
        self.collection_name = collection_name
        self.kind = "sqlite_fallback"

    @staticmethod
    def _normalize_query(text: str) -> str:
        tokens = re.findall(r"[\w\-]+", text.lower())
        return " ".join(tokens)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def query(
        self,
        query_text: str,
        n_results: int,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = self._normalize_query(query_text)
        if not normalized:
            return {"ids": [], "documents": [], "metadatas": [], "distances": []}

        limit = int(n_results)
        with self._connect() as conn:
            cursor = conn.cursor()
            like_pattern = "%" + ("%".join(normalized.split())) + "%"
            rows = cursor.execute(
                """
                SELECT DISTINCT
                    e.id AS row_id,
                    e.embedding_id AS embedding_id,
                    md.string_value AS document
                FROM embeddings e
                JOIN segments s ON e.segment_id = s.id
                JOIN collections c ON s.collection = c.id
                JOIN embedding_metadata md ON md.id = e.id AND md.key = 'chroma:document'
                WHERE c.name = ?
                  AND LOWER(md.string_value) LIKE LOWER(?)
                ORDER BY LENGTH(md.string_value) ASC
                LIMIT ?
                """,
                (self.collection_name, like_pattern, limit),
            ).fetchall()

            if not rows:
                return {"ids": [], "documents": [], "metadatas": [], "distances": []}

            row_ids = [row["row_id"] for row in rows]
            meta_rows = cursor.execute(
                f"""
                SELECT id, key, string_value, int_value, float_value, bool_value
                FROM embedding_metadata
                WHERE id IN ({','.join(['?'] * len(row_ids))})
                """,
                row_ids,
            ).fetchall()

            metadata_by_id: Dict[int, Dict[str, Any]] = {row_id: {} for row_id in row_ids}
            for meta_row in meta_rows:
                value: Any = meta_row["string_value"]
                if value is None:
                    value = meta_row["int_value"]
                if value is None:
                    value = meta_row["float_value"]
                if value is None:
                    value = meta_row["bool_value"]
                metadata_by_id.setdefault(meta_row["id"], {})[meta_row["key"]] = value

        return {
            "ids": [row["embedding_id"] for row in rows],
            "documents": [row["document"] for row in rows],
            "metadatas": [metadata_by_id.get(row["row_id"], {}) for row in rows],
            "distances": [0.5] * len(rows),
        }


def init_models_and_collection(cfg: RAGConfig) -> Tuple[BGEM3FlagModel, FlagReranker, Any]:
    embedder = BGEM3FlagModel(
        "BAAI/bge-m3",
        use_fp16=cfg.use_fp16,
        device=cfg.device,
    )

    reranker = FlagReranker(
        "BAAI/bge-reranker-v2-m3",
        use_fp16=cfg.use_fp16,
        device=cfg.device,
    )

    db_path = str(Path(cfg.chroma_persist_dir) / "chroma.sqlite3")

    try:
        if hasattr(chromadb, "PersistentClient"):
            client = chromadb.PersistentClient(path=cfg.chroma_persist_dir)
        else:
            from chromadb.config import Settings
            client = chromadb.Client(
                Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=cfg.chroma_persist_dir,
                )
            )
        collection = client.get_collection(name=cfg.collection_name)
        return embedder, reranker, collection
        
    except Exception as exc:
        print(f"[Phase4] Falling back to SQLite search backend: {exc}")
        return embedder, reranker, SQLiteFallbackCollection(db_path=db_path, collection_name=cfg.collection_name)


# -----------------------------
# Embedding (BGE-M3)
# -----------------------------
def embed_text(embedder: BGEM3FlagModel, text: str, cfg: RAGConfig) -> List[float]:
    out = embedder.encode(
        [text],
        batch_size=1,
        max_length=cfg.embed_max_length,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    return out["dense_vecs"][0].tolist()


# -----------------------------
# Chroma query by embedding
# -----------------------------
def retrieve_topk_by_embedding(
    collection: Any,
    query_embedding: List[float],
    k: int,
    where: Optional[Dict[str, Any]] = None,
    query_text: Optional[str] = None,
) -> Dict[str, Any]:
    if isinstance(collection, SQLiteFallbackCollection):
        res = collection.query(
            query_text=query_text or "",
            n_results=k,
            where=where,
        )
        return res

    res = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    return {
        "ids": res["ids"][0],
        "documents": res["documents"][0],
        "metadatas": res["metadatas"][0] if res.get("metadatas") else [None] * len(res["ids"][0]),
        "distances": res["distances"][0] if res.get("distances") else [None] * len(res["ids"][0]),
    }


# -----------------------------
# Rerank + filter
# -----------------------------
def rerank_candidates(reranker: FlagReranker, query: str, candidates: List[str]) -> List[float]:
    if not candidates:
        return []
    pairs = [(query, c) for c in candidates]
    scores = reranker.compute_score(pairs)
    return [float(s) for s in scores]


def retrieve_rerank_filter(
    embedder: BGEM3FlagModel,
    reranker: FlagReranker,
    collection: Any,
    query_for_rerank: str,
    text_for_retrieval_embedding: str,
    cfg: RAGConfig,
    k: int,
    where: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    q_emb = embed_text(embedder, text_for_retrieval_embedding, cfg)
    retrieved = retrieve_topk_by_embedding(collection, q_emb, k=k, where=where, query_text=text_for_retrieval_embedding)
    
    if not retrieved["documents"]:
        return [], {
            "k_used": k,
            "top_score": float("-inf"),
            "retrieved_ids": [],
            "retrieved_distances": [],
            "rerank_scores": [],
            "num_dense_candidates": 0,
            "num_after_filter": 0,
            "num_final": 0,
        }
    
    scores = rerank_candidates(reranker, query=query_for_rerank, candidates=retrieved["documents"])

    items: List[Dict[str, Any]] = []
    for i in range(len(scores)):
        items.append(
            {
                "dense_rank": i + 1,
                "id": retrieved["ids"][i],
                "document": retrieved["documents"][i],
                "metadata": retrieved["metadatas"][i],
                "dense_distance": retrieved["distances"][i],
                "rerank_score": float(scores[i]),
            }
        )

    items.sort(key=lambda x: x["rerank_score"], reverse=True)
    filtered = [x for x in items if x["rerank_score"] >= cfg.min_keep_score]
    final_chunks = filtered[: min(cfg.final_n, len(filtered))]

    top_score = float(items[0]["rerank_score"]) if items else float("-inf")

    debug = {
        "k_used": k,
        "top_score": top_score,
        "retrieved_ids": retrieved["ids"],
        "retrieved_distances": retrieved["distances"],
        "rerank_scores": [float(s) for s in scores],
        "num_dense_candidates": len(items),
        "num_after_filter": len(filtered),
        "num_final": len(final_chunks),
    }
    return final_chunks, debug


# -----------------------------
# HyDE via LM Studio + Safety Validation
# -----------------------------
def generate_hyde_lmstudio(query: str, cfg: RAGConfig) -> str:
    """
    Generate a short hypothetical answer/document (HyDE) in Malay, using LM Studio local server.
    Prompt is forced to be about BM grammar (tatabahasa), not electronics.
    """
    url = cfg.lmstudio_base_url.rstrip("/") + "/chat/completions"

    system = (
        "Anda ialah pembantu linguistik Bahasa Melayu (DBP). "
        "Anda hanya menjawab tentang tatabahasa, ejaan, istilah, dan penggunaan bahasa. "
        "Jangan jawab tentang elektronik, audio, atau kejuruteraan."
    )

    user = (
        f"Soalan pengguna: {query}\n\n"
        "Tulis jawapan hipotesis ringkas (3–6 ayat) berkaitan TATABAHASA Bahasa Melayu. "
        "Jika soalan mengandungi istilah seperti 'penguat', anggap maksudnya ialah 'kata penguat' "
        "(contoh: sangat, amat, sungguh, sekali, nian). "
        "Masukkan kata kunci: 'kata penguat hadapan', 'kata penguat belakang', 'kata penguat bebas', "
        "serta 1–2 contoh ayat ringkas."
        "Pastikan ejaan dan contoh ayat betul."
    )

    payload = {
        "model": cfg.lmstudio_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 240,
    }

    try:
        r = requests.post(url, json=payload, timeout=CFG.lmstudio_timeout_s)
        if not r.ok:
            print("LM Studio error:", r.status_code, r.text)
            r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"].strip()
        return text
    except Exception as e:
        print(f"[HyDE] LM Studio call failed, continuing without HyDE. Error: {e}")
        return ""


def hyde_is_valid(hyde_text: str) -> bool:
    """
    Very simple guard to reject off-domain HyDE (e.g., electronics amplifier).
    Accept if it contains grammar signals and does NOT contain electronics signals.
    """
    t = (hyde_text or "").lower()

    must_have_any = [
        "kata penguat",
        "tatabahasa",
        "ayat",
        "adjektif",
        "sangat",
        "amat",
        "sungguh",
        "sekali",
        "nian",
    ]

    bad_signals = [
        "elektrik",
        "audio",
        "isyarat",
        "pembesar suara",
        "voltan",
        "amp",
        "amplifier",
        "kuasa",
        "output",
        "input",
    ]

    return any(x in t for x in must_have_any) and not any(x in t for x in bad_signals)


def is_incomplete_spelling_question(query: str) -> bool:
    import re

    q = re.sub(r"\s+", " ", (query or "").lower().strip())
    q = q.strip(" ?.!:;")

    incomplete_exact = {
        "berikan ejaan yang betul",
        "apakah ejaan yang betul",
        "apa ejaan yang betul",
        "semak ejaan",
        "ejaan betul",
        "ejaan yang betul",
        "betulkan ejaan",
        "sila semak ejaan",
        "tolong semak ejaan",
    }

    if q in incomplete_exact:
        return True

    spelling_signals = [
        "ejaan yang betul",
        "semak ejaan",
        "ejaan betul",
        "betulkan ejaan",
    ]

    if not any(signal in q for signal in spelling_signals):
        return False

    complete_markers = [
        ",",
        " atau ",
        " bagi ",
        " untuk ",
        " perkataan ",
        "\"",
        "'",
        "“",
        "”",
    ]

    if any(marker in q for marker in complete_markers):
        return False

    return False


def is_hyde_suitable(query: str) -> bool:
    """
    Only trigger HyDE for definitional / linguistic queries.
    Avoid running HyDE for preference / opinion / permission questions.
    """
    q = query.lower()

    triggers = [
        "maksud",
        "definisi",
        "apa itu",
        "contoh",
        "tatabahasa",
        "ejaan",
        "imbuhan",
        "kata penguat",
        "morfologi",
        "istilah",
    ]

    return any(t in q for t in triggers)

# -----------------------------
# Adaptive retrieval + HyDE fallback
# -----------------------------
def adaptive_rag_retrieve_rerank(
    query: str,
    cfg: RAGConfig = CFG,
    where: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if is_incomplete_spelling_question(query):
        debug = {
            "query": query,
            "collection": cfg.collection_name,
            "expanded": False,
            "used_hyde": False,
            "hyde_selected": False,
            "prevalidation_failed": True,
            "prevalidation_reason": "incomplete_spelling_question",
            "prevalidation_answer": "Sila nyatakan perkataan yang ingin disemak ejaannya.",
            "k_small": cfg.k_small,
            "k_large": cfg.k_large,
            "min_top_score_expand": cfg.min_top_score_expand,
            "hyde_trigger_threshold": cfg.hyde_trigger_threshold,
            "min_keep_score": cfg.min_keep_score,
            "hyde_text_preview": "",
            "k_used": 0,
            "top_score": float("-inf"),
            "retrieved_ids": [],
            "retrieved_distances": [],
            "rerank_scores": [],
            "num_dense_candidates": 0,
            "num_after_filter": 0,
            "num_final": 0,
        }
        return [], debug

    embedder, reranker, collection = init_models_and_collection(cfg)

    # Pass 1: base retrieval (k_small)
    final_chunks, dbg = retrieve_rerank_filter(
        embedder=embedder,
        reranker=reranker,
        collection=collection,
        query_for_rerank=query,
        text_for_retrieval_embedding=query,
        cfg=cfg,
        k=cfg.k_small,
        where=where,
    )

    expanded = False
    used_hyde = False
    hyde_text = ""
    hyde_selected = False
    hyde_dbg_summary = {}

    # Pass 2: expand retrieval if weak
    if dbg["top_score"] < cfg.min_top_score_expand:
        final_chunks, dbg = retrieve_rerank_filter(
            embedder=embedder,
            reranker=reranker,
            collection=collection,
            query_for_rerank=query,
            text_for_retrieval_embedding=query,
            cfg=cfg,
            k=cfg.k_large,
            where=where,
        )
        expanded = True

    # Pass 3: HyDE fallback if still weak OR no usable chunks
    #if (dbg["num_after_filter"] < 2) or (dbg["top_score"] < cfg.hyde_trigger_threshold):
    weak_retrieval = (
        (dbg["num_after_filter"] < 2)
        or (dbg["top_score"] < cfg.hyde_trigger_threshold)
    )

    if weak_retrieval and is_hyde_suitable(query):
        hyde_text = generate_hyde_lmstudio(query, cfg)

        if hyde_text and hyde_is_valid(hyde_text):
            hyde_chunks, hyde_dbg = retrieve_rerank_filter(
                embedder=embedder,
                reranker=reranker,
                collection=collection,
                query_for_rerank=query,                  # rerank against original query
                text_for_retrieval_embedding=hyde_text,   # retrieval uses HyDE embedding
                cfg=cfg,
                k=cfg.k_large,
                where=where,
            )
            used_hyde = True

            # Save HyDE summary for debugging / thesis
            hyde_dbg_summary = {
                "hyde_top_score": hyde_dbg["top_score"],
                "hyde_num_dense_candidates": hyde_dbg["num_dense_candidates"],
                "hyde_num_after_filter": hyde_dbg["num_after_filter"],
                "hyde_num_final": hyde_dbg["num_final"],
                "hyde_k_used": hyde_dbg["k_used"],
            }

            # Choose HyDE results if it improves either top_score or usable count
            if (hyde_dbg["top_score"] > dbg["top_score"]) or (hyde_dbg["num_after_filter"] > dbg["num_after_filter"]):
                final_chunks, dbg = hyde_chunks, hyde_dbg
                hyde_selected = True
        else:
            if hyde_text:
                print("[HyDE] Discarded hyde_text (off-domain / failed validation).")
            hyde_text = ""

    debug = {
        "query": query,
        "collection": cfg.collection_name,
        "expanded": expanded,
        "used_hyde": used_hyde,
        "hyde_selected": hyde_selected,
        "k_small": cfg.k_small,
        "k_large": cfg.k_large,
        "min_top_score_expand": cfg.min_top_score_expand,
        "hyde_trigger_threshold": cfg.hyde_trigger_threshold,
        "min_keep_score": cfg.min_keep_score,
        "hyde_text_preview": hyde_text[:400] + ("..." if len(hyde_text) > 400 else ""),
        **hyde_dbg_summary,
        **dbg,
    }
    return final_chunks, debug


# -----------------------------
# Phase 5 context formatting helper
# -----------------------------
def format_context(final_chunks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for i, ch in enumerate(final_chunks, start=1):
        meta = ch.get("metadata") or {}
        kategori = meta.get("kategori", "")

        if kategori:
            parts.append(f"[{i}] Kategori: {kategori}")
        else:
            parts.append(f"[{i}]")

        document = ch.get("document", "") or ""

        document = re.sub(r"\b(?:doc_id|chroma_id|original_id|atomic_id)\s*=\s*[^\s,;|]+", "", document, flags=re.IGNORECASE)
        document = re.sub(r"\bmetadata\s*[:=]\s*\{[^\}]*\}", "", document, flags=re.IGNORECASE)
        document = re.sub(r"[ \t]{2,}", " ", document)
        document = re.sub(r"\n{3,}", "\n\n", document)

        parts.append(document.strip())
        parts.append("")

    return "\n".join(parts).strip()


# -----------------------------
# Phase 4 public API (for Phase 5)
# -----------------------------
def phase4_get_context_chunks(
    query: str,
    cfg: RAGConfig = CFG,
    where: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Clean wrapper for Phase 5.
    Returns:
        final_chunks: List[dict]
        debug: dict
    """
    final_chunks, debug = adaptive_rag_retrieve_rerank(
        query=query,
        cfg=cfg,
        where=where,
    )
    return final_chunks, debug

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    # Try different queries here
    user_query = "Soalan contoh dengan kata penguat hadapan dan kata penguat bebas."

    final_chunks, debug = adaptive_rag_retrieve_rerank(user_query)

    print("\n=== FINAL CHUNKS (for prompt context) ===")
    for i, ch in enumerate(final_chunks, start=1):
        print(f"\n[{i}] rerank_score={ch['rerank_score']:.4f}  id={ch['id']}")
        text = ch.get("document") or ""
        print(text if len(text) < 900 else text[:900] + " ...")
        if ch.get("metadata"):
            print("metadata:", ch["metadata"])

    print("\n=== CONTEXT STRING (Phase 5 prompt injection) ===")
    print(format_context(final_chunks))

    print("\n=== DEBUG (dense retrieval order) ===")
    print(
        f"expanded={debug['expanded']}  used_hyde={debug['used_hyde']}  hyde_selected={debug['hyde_selected']}  "
        f"k_small={debug['k_small']}  k_large={debug['k_large']}  "
        f"top_score={debug['top_score']:.4f}  "
        f"min_top_score_expand={debug['min_top_score_expand']}  "
        f"hyde_trigger_threshold={debug['hyde_trigger_threshold']}  "
        f"min_keep_score={debug['min_keep_score']}"
    )

    for i in range(len(debug["retrieved_ids"])):
        dist = debug["retrieved_distances"][i]
        score = debug["rerank_scores"][i]
        doc_id = debug["retrieved_ids"][i]
        print(f"{i+1}. dense_distance={dist}  rerank_score={score:.4f}  id={doc_id}")

    print(
        f"candidates={debug['num_dense_candidates']}  "
        f"after_filter={debug['num_after_filter']}  "
        f"final={debug['num_final']}"
    )

    if debug["used_hyde"]:
        print(
            f"hyde_top_score={debug.get('hyde_top_score')}  "
            f"hyde_after_filter={debug.get('hyde_num_after_filter')}  "
            f"hyde_final={debug.get('hyde_num_final')}  "
            f"hyde_k_used={debug.get('hyde_k_used')}"
        )

    if debug["hyde_text_preview"]:
        print("\n=== HyDE TEXT PREVIEW ===")
        print(debug["hyde_text_preview"])