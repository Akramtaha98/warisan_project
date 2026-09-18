import json
from pathlib import Path
import tempfile
import unittest

from app import build_sample_chroma as builder


class SampleQaDataTests(unittest.TestCase):
    def test_fixture_is_complete_unique_malay_qa(self):
        payload = json.loads(builder.DEFAULT_INPUT.read_text(encoding="utf-8"))
        records = builder.load_records(builder.DEFAULT_INPUT)

        self.assertEqual(payload["language"], "ms")
        self.assertEqual(payload["license"], "CC0-1.0")
        self.assertIn("sintetik", payload["description"].lower())
        self.assertEqual(len(records), 100)
        self.assertEqual(len({record["id"] for record in records}), len(records))
        self.assertGreaterEqual(len({record["category"] for record in records}), 30)
        self.assertGreaterEqual(sum(record["difficulty"] == "hard" for record in records), 12)
        for record in records:
            self.assertTrue(record["question"].endswith("?"))
            self.assertGreaterEqual(len(record["answer"].split()), 8)
            document = builder.format_document(record)
            self.assertIn("Soalan:", document)
            self.assertIn("Jawapan:", document)

    def test_duplicate_or_incomplete_records_are_rejected(self):
        payload = {
            "language": "ms",
            "records": [
                {"id": "sama", "category": "x", "question": "Soalan?", "answer": "Jawapan lengkap untuk ujian."},
                {"id": "sama", "category": "x", "question": "Soalan lain?", "answer": "Jawapan kedua untuk ujian."},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(builder.SampleDataError, "ID pendua"):
                builder.load_records(path)


class FakeCollection:
    def __init__(self):
        self.add_calls = []

    def add(self, **kwargs):
        self.add_calls.append(kwargs)

    def count(self):
        return sum(len(call["ids"]) for call in self.add_calls)


class FakeClient:
    def __init__(self, existing=False):
        self.existing = existing
        self.created = None
        self.deleted = []
        self.collection = FakeCollection()

    def list_collections(self):
        if not self.existing:
            return []
        return [type("CollectionName", (), {"name": builder.SAMPLE_COLLECTION})()]

    def delete_collection(self, *, name):
        self.deleted.append(name)
        self.existing = False

    def create_collection(self, **kwargs):
        self.created = kwargs
        return self.collection


class FakeModel:
    def __init__(self):
        self.calls = []

    def encode(self, documents, **kwargs):
        self.calls.append((documents, kwargs))
        return {"dense_vecs": [[float(index), 0.5, 1.0] for index, _ in enumerate(documents)]}


class SampleChromaBuilderTests(unittest.TestCase):
    def test_compose_override_mounts_only_the_sample_read_only(self):
        root = Path(__file__).resolve().parents[1]
        compose = (root / "docker-compose.sample.yml").read_text(encoding="utf-8")
        dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("CHROMA_COLLECTION_NAME: dbp_malay_qa_sample", compose)
        self.assertIn("./data/sample_chroma_db:/app/data/chroma_db:ro", compose)
        self.assertNotIn("./data/chroma_db:/app/data/chroma_db", compose)
        self.assertIn("data/sample_chroma_db", dockerignore.splitlines())

    def test_builder_batches_bge_m3_documents_and_metadata(self):
        fake_client = FakeClient()
        fake_model = FakeModel()
        model_calls = []

        def model_factory(name, **kwargs):
            model_calls.append((name, kwargs))
            return fake_model

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = builder.build_sample_collection(
                output_dir=root / "sample",
                production_dir=root / "production",
                batch_size=7,
                client_factory=lambda **_: fake_client,
                model_factory=model_factory,
            )

        records = builder.load_records(builder.DEFAULT_INPUT)
        self.assertEqual(result["count"], len(records))
        self.assertEqual(result["collection"], builder.SAMPLE_COLLECTION)
        self.assertEqual(model_calls, [(builder.MODEL_NAME, {"use_fp16": False, "device": "cpu"})])
        self.assertEqual(fake_client.created["metadata"]["embedding_model"], builder.MODEL_NAME)
        self.assertEqual(fake_client.created["metadata"]["hnsw:space"], "cosine")
        self.assertEqual(len(fake_client.collection.add_calls), (len(records) + 6) // 7)
        first = fake_client.collection.add_calls[0]
        self.assertTrue(first["documents"][0].startswith("Soalan:"))
        self.assertEqual(first["metadatas"][0]["sumber"], "synthetic_project_fixture")
        self.assertEqual(first["metadatas"][0]["kesukaran"], "standard")
        self.assertEqual(len(first["embeddings"][0]), 3)

    def test_builder_refuses_production_path_and_collection_name(self):
        with tempfile.TemporaryDirectory() as directory:
            production = Path(directory) / "chroma_db"
            with self.assertRaisesRegex(builder.SampleDataError, "produksi"):
                builder.validate_target(production, builder.SAMPLE_COLLECTION, production)
            with self.assertRaisesRegex(builder.SampleDataError, "produksi"):
                builder.validate_target(
                    Path(directory) / "sample",
                    builder.PRODUCTION_COLLECTION,
                    production,
                )

    def test_existing_sample_requires_explicit_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(builder.SampleDataError, "--replace"):
                builder.build_sample_collection(
                    output_dir=root / "sample",
                    production_dir=root / "production",
                    client_factory=lambda **_: FakeClient(existing=True),
                    model_factory=lambda *_args, **_kwargs: FakeModel(),
                )

            client = FakeClient(existing=True)
            result = builder.build_sample_collection(
                output_dir=root / "sample-replace",
                production_dir=root / "production",
                replace=True,
                client_factory=lambda **_: client,
                model_factory=lambda *_args, **_kwargs: FakeModel(),
            )
            self.assertEqual(client.deleted, [builder.SAMPLE_COLLECTION])
            self.assertGreater(result["count"], 0)


if __name__ == "__main__":
    unittest.main()
