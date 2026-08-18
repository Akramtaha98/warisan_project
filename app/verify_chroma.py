#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import chromadb

path = os.getenv("CHROMA_PERSIST_DIR", "/app/data/chroma_db")
name = os.getenv("CHROMA_COLLECTION_NAME", "dbp_khidmatnasihat_clean_atomic")
expected = int(os.getenv("CHROMA_EXPECTED_COUNT", "33320"))

db = Path(path) / "chroma.sqlite3"
if not db.exists():
    print(f"ERROR: Missing {db}")
    sys.exit(2)

try:
    client = chromadb.PersistentClient(path=path)
    collection = client.get_collection(name=name)
    count = collection.count()
except Exception as exc:
    print(f"ERROR: Could not open Chroma collection '{name}': {exc}")
    sys.exit(3)

print(f"Chroma path       : {path}")
print(f"Collection        : {name}")
print(f"Document count    : {count}")
print(f"Expected count    : {expected}")
if count != expected:
    print("ERROR: Collection count does not match the thesis final collection.")
    sys.exit(4)
print("OK: ChromaDB final collection verified.")
