from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


SCRIPTS = Path(__file__).resolve().parents[1] / "app" / "scripts"
sys.path.insert(0, str(SCRIPTS))

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.RequestException = Exception
    requests_stub.post = MagicMock()
    sys.modules["requests"] = requests_stub

import phase4_retrieval_rerank as rag


def retrieval_debug(score, count, k):
    return {
        "k_used": k,
        "top_score": score,
        "retrieved_ids": ["id"],
        "retrieved_distances": [0.1],
        "rerank_scores": [score],
        "num_dense_candidates": count,
        "num_after_filter": count,
        "num_final": min(count, 6),
    }


class RetrievalPolicyTests(unittest.TestCase):
    def test_defaults_match_broader_retrieval_policy(self):
        cfg = rag.RAGConfig()
        self.assertEqual((cfg.k_small, cfg.k_large, cfg.final_n), (15, 40, 6))
        self.assertLessEqual(cfg.answer_min_score, cfg.hyde_trigger_threshold)
        self.assertLess(cfg.hyde_trigger_threshold, cfg.min_top_score_expand)

    def test_medium_confidence_expands_instead_of_being_rejected_early(self):
        cfg = rag.RAGConfig()
        chunk = {"id": "x", "document": "penggunaan ialah dan adalah", "metadata": {}}
        with patch.object(rag, "init_models_and_collection", return_value=(1, 2, 3)), patch.object(
            rag,
            "retrieve_rerank_filter",
            side_effect=[
                ([chunk], retrieval_debug(1.2, 1, cfg.k_small)),
                ([chunk] * 6, retrieval_debug(1.3, 6, cfg.k_large)),
            ],
        ) as retrieve:
            chunks, debug = rag.adaptive_rag_retrieve_rerank(
                "Apakah penggunaan ialah dan adalah?", cfg
            )
        self.assertTrue(debug["expanded"])
        self.assertEqual(len(chunks), 6)
        self.assertEqual([call.args[6] for call in retrieve.call_args_list], [15, 40])

    def test_filter_returns_at_most_six_best_chunks(self):
        cfg = rag.RAGConfig()
        embedder = MagicMock()
        embedder.encode.return_value = {"dense_vecs": [MagicMock(tolist=lambda: [0.1])]}
        reranker = MagicMock()
        reranker.compute_score.return_value = list(range(10))
        collection = MagicMock()
        collection.query.return_value = {
            "ids": [[f"id-{index}" for index in range(10)]],
            "documents": [[f"dokumen-{index}" for index in range(10)]],
            "metadatas": [[{} for _ in range(10)]],
            "distances": [[0.1 for _ in range(10)]],
        }
        chunks, _ = rag.retrieve_rerank_filter(
            embedder, reranker, collection, "soalan", "soalan", cfg, 15
        )
        self.assertEqual(len(chunks), 6)
        self.assertEqual(chunks[0]["rerank_score"], 9.0)


class HydeAndResourceTests(unittest.TestCase):
    def tearDown(self):
        rag.init_models_and_collection.cache_clear()

    def test_hyde_prompt_keeps_actual_query_and_has_no_forced_topic(self):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "Ialah dan adalah mempunyai fungsi berbeza dalam ayat."}}]
        }
        query = "Apakah perbezaan ialah dengan adalah?"
        with patch.object(rag.requests, "post", return_value=response) as post:
            text = rag.generate_hyde_lmstudio(query)
        user_prompt = post.call_args.kwargs["json"]["messages"][1]["content"]
        self.assertIn(query, user_prompt)
        self.assertNotIn("kata penguat hadapan", user_prompt)
        self.assertTrue(rag.hyde_is_valid(text, query))
        self.assertFalse(
            rag.hyde_is_valid("Kata penguat menerangkan tahap kata adjektif dalam ayat.", query)
        )

    def test_resources_are_cached_and_chroma_failure_is_not_silenced(self):
        embedder_ctor = MagicMock(return_value=object())
        reranker_ctor = MagicMock(return_value=object())
        collection = object()
        client = MagicMock()
        client.get_collection.return_value = collection
        chromadb = types.ModuleType("chromadb")
        chromadb.PersistentClient = MagicMock(return_value=client)
        flag = types.ModuleType("FlagEmbedding")
        flag.BGEM3FlagModel = embedder_ctor
        flag.FlagReranker = reranker_ctor
        cfg = rag.RAGConfig(chroma_persist_dir="/tmp/dbp-test")

        with patch.dict(sys.modules, {"chromadb": chromadb, "FlagEmbedding": flag}):
            first = rag.init_models_and_collection(cfg)
            second = rag.init_models_and_collection(cfg)
        self.assertIs(first, second)
        embedder_ctor.assert_called_once()
        reranker_ctor.assert_called_once()
        chromadb.PersistentClient.assert_called_once()

        rag.init_models_and_collection.cache_clear()
        client.get_collection.side_effect = OSError("missing collection")
        with patch.dict(sys.modules, {"chromadb": chromadb, "FlagEmbedding": flag}):
            with self.assertRaisesRegex(RuntimeError, "ChromaDB tidak dapat dimuatkan"):
                rag.init_models_and_collection(
                    rag.RAGConfig(chroma_persist_dir="/tmp/dbp-test-missing")
                )
