#!/usr/bin/env python3
"""Build the isolated Malay QA development collection with BGE-M3 embeddings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Iterable


SAMPLE_COLLECTION = "dbp_malay_qa_sample"
PRODUCTION_COLLECTION = "dbp_khidmatnasihat_clean_atomic"
MODEL_NAME = "BAAI/bge-m3"
DEFAULT_INPUT = Path(__file__).resolve().parent / "sample_data" / "malay_qa.json"
DEFAULT_OUTPUT = Path.cwd() / "data" / "sample_chroma_db"
PRODUCTION_DIR = Path.cwd() / "data" / "chroma_db"
REQUIRED_FIELDS = ("id", "category", "question", "answer")


class SampleDataError(ValueError):
    """Raised when the source fixture or requested target is unsafe."""


def load_records(path: Path) -> list[dict[str, str]]:
    """Load and validate the versioned QA fixture before any DB is opened."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SampleDataError(f"Tidak dapat membaca data sampel: {path}") from exc

    if not isinstance(payload, dict) or payload.get("language") != "ms":
        raise SampleDataError("Data sampel mesti menggunakan bahasa 'ms'.")

    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise SampleDataError("Data sampel tidak mengandungi rekod QA.")

    seen_ids: set[str] = set()
    validated: list[dict[str, str]] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise SampleDataError(f"Rekod {index} bukan objek JSON.")
        missing = [
            field
            for field in REQUIRED_FIELDS
            if not isinstance(record.get(field), str) or not record[field].strip()
        ]
        if missing:
            raise SampleDataError(
                f"Rekod {index} tiada medan teks: {', '.join(missing)}."
            )
        record_id = record["id"].strip()
        if record_id in seen_ids:
            raise SampleDataError(f"ID pendua ditemui: {record_id}")
        seen_ids.add(record_id)
        validated.append({field: record[field].strip() for field in REQUIRED_FIELDS})
    return validated


def format_document(record: dict[str, str]) -> str:
    """Create the exact text embedded and later passed to the answer model."""

    return f"Soalan: {record['question']}\nJawapan: {record['answer']}"


def _collection_names(collections: Iterable[Any]) -> set[str]:
    return {
        item if isinstance(item, str) else str(getattr(item, "name", ""))
        for item in collections
    }


def validate_target(
    output_dir: Path,
    collection_name: str,
    production_dir: Path = PRODUCTION_DIR,
) -> None:
    """Prevent sample generation from touching production data or its name."""

    output = output_dir.expanduser().resolve()
    production = production_dir.expanduser().resolve()
    if output == production or production in output.parents:
        raise SampleDataError(
            "Sasaran sampel tidak boleh berada di dalam data/chroma_db produksi."
        )
    if collection_name == PRODUCTION_COLLECTION:
        raise SampleDataError("Nama koleksi produksi tidak boleh digunakan untuk sampel.")
    if collection_name != SAMPLE_COLLECTION:
        raise SampleDataError(
            f"Gunakan nama koleksi sampel tetap: {SAMPLE_COLLECTION}"
        )


def _default_client_factory(*, path: str) -> Any:
    import chromadb

    return chromadb.PersistentClient(path=path)


def _default_model_factory(model_name: str, **kwargs: Any) -> Any:
    from FlagEmbedding import BGEM3FlagModel

    return BGEM3FlagModel(model_name, **kwargs)


def build_sample_collection(
    *,
    input_path: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT,
    collection_name: str = SAMPLE_COLLECTION,
    batch_size: int = 16,
    device: str = "cpu",
    use_fp16: bool = False,
    replace: bool = False,
    production_dir: Path = PRODUCTION_DIR,
    client_factory: Callable[..., Any] | None = None,
    model_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Embed the fixture and persist it as an isolated Chroma collection."""

    if batch_size < 1:
        raise SampleDataError("Saiz kelompok mesti sekurang-kurangnya 1.")
    validate_target(output_dir, collection_name, production_dir)
    records = load_records(input_path)

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    client_factory = client_factory or _default_client_factory
    model_factory = model_factory or _default_model_factory
    client = client_factory(path=str(output_dir))

    existing = _collection_names(client.list_collections())
    if collection_name in existing:
        if not replace:
            raise SampleDataError(
                f"Koleksi '{collection_name}' sudah wujud. Gunakan --replace untuk membinanya semula."
            )
        client.delete_collection(name=collection_name)

    model = model_factory(MODEL_NAME, use_fp16=use_fp16, device=device)
    collection = client.create_collection(
        name=collection_name,
        metadata={
            "hnsw:space": "cosine",
            "language": "ms",
            "purpose": "development-test-only",
            "embedding_model": MODEL_NAME,
        },
    )

    for offset in range(0, len(records), batch_size):
        batch = records[offset : offset + batch_size]
        documents = [format_document(record) for record in batch]
        encoded = model.encode(
            documents,
            batch_size=batch_size,
            max_length=512,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )["dense_vecs"]
        embeddings = [
            vector.tolist() if hasattr(vector, "tolist") else list(vector)
            for vector in encoded
        ]
        collection.add(
            ids=[record["id"] for record in batch],
            documents=documents,
            embeddings=embeddings,
            metadatas=[
                {
                    "doc_id": record["id"],
                    "kategori": record["category"],
                    "bahasa": "ms",
                    "sumber": "synthetic_project_fixture",
                    "jenis": "qa_sample",
                }
                for record in batch
            ],
        )

    actual_count = collection.count()
    if actual_count != len(records):
        raise RuntimeError(
            f"Bilangan rekod Chroma tidak sepadan: {actual_count}/{len(records)}"
        )
    return {
        "path": str(output_dir),
        "collection": collection_name,
        "count": actual_count,
        "embedding_model": MODEL_NAME,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bina ChromaDB QA Bahasa Melayu yang berasingan untuk ujian."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--collection", default=SAMPLE_COLLECTION)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--use-fp16", action="store_true")
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build_sample_collection(
            input_path=args.input,
            output_dir=args.output,
            collection_name=args.collection,
            batch_size=args.batch_size,
            device=args.device,
            use_fp16=args.use_fp16,
            replace=args.replace,
        )
    except (SampleDataError, RuntimeError) as exc:
        print(f"RALAT: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("ChromaDB sampel berjaya dibina.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
