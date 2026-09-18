"""DBP retrieval pipeline: dense retrieval, reranking, adaptive expansion and HyDE.

The collection stores BGE-M3 dense vectors, so query embeddings are produced here
and passed directly to Chroma. Expensive models and the collection are cached for
the lifetime of the application process.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests


LOGGER = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class RAGConfig:
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "/app/data/chroma_db")
    collection_name: str = os.getenv(
        "CHROMA_COLLECTION_NAME", "dbp_khidmatnasihat_clean_atomic"
    )

    # Broad enough for comparisons and multi-part questions; reranking still
    # controls which chunks enter the prompt.
    final_n: int = _env_int("RAG_FINAL_N", 6)
    k_small: int = _env_int("RAG_K_SMALL", 15)
    k_large: int = _env_int("RAG_K_LARGE", 40)
    min_keep_score: float = _env_float("RAG_MIN_KEEP_SCORE", 0.8)

    # No confidence gap: medium results expand, weak expanded results get HyDE,
    # and answer_min_score is the one final refusal threshold.
    min_top_score_expand: float = _env_float("RAG_EXPAND_SCORE", 1.5)
    hyde_trigger_threshold: float = _env_float("RAG_HYDE_SCORE", 1.0)
    answer_min_score: float = _env_float("RAG_ANSWER_SCORE", 0.8)

    device: str = os.getenv("RAG_DEVICE", "cpu")
    use_fp16: bool = os.getenv("RAG_USE_FP16", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    embed_max_length: int = _env_int("RAG_EMBED_MAX_LENGTH", 512)
    embed_batch_size: int = _env_int("RAG_EMBED_BATCH_SIZE", 16)

    lmstudio_base_url: str = os.getenv(
        "LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1/"
    )
    lmstudio_model: str = os.getenv("LMSTUDIO_MODEL", "Qwen/Qwen3-8B")
    lmstudio_timeout_s: int = _env_int("LMSTUDIO_TIMEOUT_S", 120)


CFG = RAGConfig()


@lru_cache(maxsize=4)
def init_models_and_collection(cfg: RAGConfig = CFG) -> Tuple[Any, Any, Any]:
    """Load RAG resources once per distinct immutable configuration.

    Chroma failures are fatal. A silent substring-search fallback made valid
    paraphrased questions look unsupported and hid deployment problems.
    """

    import chromadb
    from FlagEmbedding import BGEM3FlagModel, FlagReranker

    try:
        client = chromadb.PersistentClient(path=cfg.chroma_persist_dir)
        collection = client.get_collection(name=cfg.collection_name)
    except Exception as exc:
        raise RuntimeError(
            "ChromaDB tidak dapat dimuatkan. Semak CHROMA_PERSIST_DIR dan "
            f"koleksi '{cfg.collection_name}'."
        ) from exc
    embedder = BGEM3FlagModel(
        "BAAI/bge-m3", use_fp16=cfg.use_fp16, device=cfg.device
    )
    reranker = FlagReranker(
        "BAAI/bge-reranker-v2-m3", use_fp16=cfg.use_fp16, device=cfg.device
    )
    return embedder, reranker, collection


def embed_text(embedder: Any, text: str, cfg: RAGConfig) -> List[float]:
    output = embedder.encode(
        [text],
        batch_size=1,
        max_length=cfg.embed_max_length,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    return output["dense_vecs"][0].tolist()


def retrieve_topk_by_embedding(
    collection: Any,
    query_embedding: List[float],
    k: int,
    where: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    return {
        "ids": ids,
        "documents": documents,
        "metadatas": result.get("metadatas", [[]])[0] or [None] * len(ids),
        "distances": result.get("distances", [[]])[0] or [None] * len(ids),
    }


def rerank_candidates(reranker: Any, query: str, candidates: List[str]) -> List[float]:
    if not candidates:
        return []
    scores = reranker.compute_score([(query, candidate) for candidate in candidates])
    if isinstance(scores, (int, float)):
        scores = [scores]
    return [float(score) for score in scores]


def retrieve_rerank_filter(
    embedder: Any,
    reranker: Any,
    collection: Any,
    query_for_rerank: str,
    text_for_retrieval_embedding: str,
    cfg: RAGConfig,
    k: int,
    where: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    query_embedding = embed_text(embedder, text_for_retrieval_embedding, cfg)
    retrieved = retrieve_topk_by_embedding(collection, query_embedding, k, where)
    scores = rerank_candidates(reranker, query_for_rerank, retrieved["documents"])
    items = [
        {
            "dense_rank": index + 1,
            "id": retrieved["ids"][index],
            "document": retrieved["documents"][index],
            "metadata": retrieved["metadatas"][index],
            "dense_distance": retrieved["distances"][index],
            "rerank_score": score,
        }
        for index, score in enumerate(scores)
    ]
    items.sort(key=lambda item: item["rerank_score"], reverse=True)
    filtered = [item for item in items if item["rerank_score"] >= cfg.min_keep_score]
    final_chunks = filtered[: cfg.final_n]
    top_score = items[0]["rerank_score"] if items else float("-inf")
    return final_chunks, {
        "k_used": k,
        "top_score": top_score,
        "retrieved_ids": retrieved["ids"],
        "retrieved_distances": retrieved["distances"],
        "rerank_scores": scores,
        "num_dense_candidates": len(items),
        "num_after_filter": len(filtered),
        "num_final": len(final_chunks),
    }


def generate_hyde_lmstudio(query: str, cfg: RAGConfig = CFG) -> str:
    """Generate a short hypothetical DBP-style passage about the actual query."""

    payload = {
        "model": cfg.lmstudio_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Anda membantu pencarian dalam pangkalan data bahasa Melayu. "
                    "Hasilkan petikan hipotesis yang mungkin menjawab soalan pengguna. "
                    "Kekalkan topik, istilah dan maksud asal. Jangan tambahkan topik "
                    "tatabahasa yang tidak ditanya. /no_think"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Soalan:\n{query}\n\nTulis 2 hingga 4 ayat Bahasa Melayu formal "
                    "dengan kata kunci yang berkaitan secara langsung dengan soalan ini."
                ),
            },
        ],
        "temperature": 0.2,
        "top_p": 0.8,
        "max_tokens": 240,
    }
    try:
        response = requests.post(
            cfg.lmstudio_base_url.rstrip("/") + "/chat/completions",
            json=payload,
            timeout=cfg.lmstudio_timeout_s,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        LOGGER.warning("HyDE tidak dapat dijana; carian asal dikekalkan: %s", exc)
        return ""


_HYDE_STOPWORDS = {
    "yang", "dan", "atau", "untuk", "dengan", "dalam", "apakah",
    "bagaimanakah", "antara", "bahasa", "melayu", "kata", "boleh", "betul",
}


def _meaningful_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\w-]+", text.lower(), flags=re.UNICODE)
        if len(token) >= 3 and token not in _HYDE_STOPWORDS
    }


def hyde_is_valid(hyde_text: str, query: str) -> bool:
    """Require query-term overlap so an unrelated hypothetical passage is rejected."""

    if len((hyde_text or "").split()) < 5:
        return False
    query_terms = _meaningful_terms(query)
    hyde_terms = _meaningful_terms(hyde_text)
    return bool(query_terms and query_terms & hyde_terms)


def is_incomplete_spelling_question(query: str) -> bool:
    normalized = re.sub(r"\s+", " ", (query or "").lower().strip()).strip(" ?.!:;")
    return normalized in {
        "berikan ejaan yang betul", "apakah ejaan yang betul",
        "apa ejaan yang betul", "semak ejaan", "ejaan betul",
        "ejaan yang betul", "betulkan ejaan", "sila semak ejaan",
        "tolong semak ejaan",
    }


def is_hyde_suitable(query: str) -> bool:
    query_lower = query.lower()
    language_signals = (
        "maksud", "makna", "definisi", "erti", "contoh", "tatabahasa",
        "ejaan", "imbuhan", "istilah", "penggunaan", "guna", "ayat",
        "perbezaan", "beza", "mana yang betul", "bentuk yang betul",
    )
    return any(signal in query_lower for signal in language_signals)


def _empty_debug(query: str, cfg: RAGConfig) -> Dict[str, Any]:
    return {
        "query": query,
        "collection": cfg.collection_name,
        "expanded": False,
        "used_hyde": False,
        "hyde_selected": False,
        "k_small": cfg.k_small,
        "k_large": cfg.k_large,
        "min_top_score_expand": cfg.min_top_score_expand,
        "hyde_trigger_threshold": cfg.hyde_trigger_threshold,
        "answer_min_score": cfg.answer_min_score,
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


def adaptive_rag_retrieve_rerank(
    query: str,
    cfg: RAGConfig = CFG,
    where: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if is_incomplete_spelling_question(query):
        debug = _empty_debug(query, cfg)
        debug.update(
            prevalidation_failed=True,
            prevalidation_reason="incomplete_spelling_question",
            prevalidation_answer="Sila nyatakan perkataan yang ingin disemak ejaannya.",
        )
        return [], debug

    embedder, reranker, collection = init_models_and_collection(cfg)
    chunks, retrieval_debug = retrieve_rerank_filter(
        embedder, reranker, collection, query, query, cfg, cfg.k_small, where
    )
    expanded = False
    if (
        retrieval_debug["top_score"] < cfg.min_top_score_expand
        or retrieval_debug["num_final"] < cfg.final_n
    ):
        chunks, retrieval_debug = retrieve_rerank_filter(
            embedder, reranker, collection, query, query, cfg, cfg.k_large, where
        )
        expanded = True

    used_hyde = False
    hyde_selected = False
    hyde_text = ""
    hyde_debug: Dict[str, Any] = {}
    weak_retrieval = (
        retrieval_debug["top_score"] < cfg.hyde_trigger_threshold
        or retrieval_debug["num_after_filter"] < 2
    )
    if weak_retrieval and is_hyde_suitable(query):
        hyde_text = generate_hyde_lmstudio(query, cfg)
        if hyde_is_valid(hyde_text, query):
            used_hyde = True
            hyde_chunks, candidate_debug = retrieve_rerank_filter(
                embedder, reranker, collection, query, hyde_text, cfg, cfg.k_large, where
            )
            hyde_debug = {
                "hyde_top_score": candidate_debug["top_score"],
                "hyde_num_after_filter": candidate_debug["num_after_filter"],
                "hyde_num_final": candidate_debug["num_final"],
                "hyde_k_used": candidate_debug["k_used"],
            }
            if (
                candidate_debug["top_score"] > retrieval_debug["top_score"]
                or candidate_debug["num_after_filter"]
                > retrieval_debug["num_after_filter"]
            ):
                chunks, retrieval_debug = hyde_chunks, candidate_debug
                hyde_selected = True

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
        "answer_min_score": cfg.answer_min_score,
        "min_keep_score": cfg.min_keep_score,
        "hyde_text_preview": hyde_text[:400],
        **hyde_debug,
        **retrieval_debug,
    }
    return chunks, debug


def format_context(final_chunks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for index, chunk in enumerate(final_chunks, start=1):
        category = (chunk.get("metadata") or {}).get("kategori", "")
        parts.append(f"[{index}]" + (f" Kategori: {category}" if category else ""))
        document = chunk.get("document", "") or ""
        document = re.sub(
            r"\b(?:doc_id|chroma_id|original_id|atomic_id)\s*=\s*[^\s,;|]+",
            "", document, flags=re.IGNORECASE,
        )
        document = re.sub(
            r"\bmetadata\s*[:=]\s*\{[^}]*\}", "", document, flags=re.IGNORECASE
        )
        parts.extend((re.sub(r"[ \t]{2,}", " ", document).strip(), ""))
    return "\n".join(parts).strip()


def phase4_get_context_chunks(
    query: str,
    cfg: RAGConfig = CFG,
    where: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return adaptive_rag_retrieve_rerank(query, cfg, where)


if __name__ == "__main__":
    sample_chunks, sample_debug = adaptive_rag_retrieve_rerank(
        "Apakah perbezaan antara 'ialah' dengan 'adalah'?"
    )
    print(format_context(sample_chunks))
    print(sample_debug)
