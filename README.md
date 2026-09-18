# DBP Bahasa Melayu Advisory Chatbot

A retrieval-augmented chatbot answering Malay-language advisory questions from the
Khidmat Nasihat Bahasa knowledge base of Dewan Bahasa dan Pustaka. Built as an
academic prototype: dense retrieval, reranking, selective HyDE, context validation,
and a locally-hosted LLM.

Everything runs locally. No cloud services, no API keys.

## Quick start

```bash
./deploy.sh
```

That is the whole deployment. It detects the machine's GPU group IDs, writes `.env`,
builds and starts both containers, verifies the knowledge base, and prints the URL.
Safe to re-run.

| Command | What it does |
|---|---|
| `./deploy.sh` | Full deploy, re-runnable |
| `./deploy.sh check` | Preflight only, changes nothing |
| `./deploy.sh status` | Container status |
| `./deploy.sh logs` | Follow logs |
| `./deploy.sh stop` | Stop only this project |

**Full deployment guide, verification steps and troubleshooting: [`README_DEPLOY.md`](README_DEPLOY.md).**

## Architecture

```
dbp-chatbot   Streamlit UI + BGE-M3 embeddings + BGE reranker + ChromaDB client   (CPU)
     |
     |  http://llm:8080/v1/   private Docker network, never published to the LAN
     v
dbp-llm       llama.cpp Vulkan server + Gemma 3 4B IT (Q4_K_M GGUF)               (GPU)
```

Target hardware is an AMD Radeon iGPU (tested on a GMKtec EVO-X2, Ryzen AI Max+ 395 /
Radeon 8060S) using the Vulkan backend. No ROCm or CUDA is required or wanted.

## Getting the knowledge base

The ChromaDB collection is **not in this repository** — it is roughly 676 MB, which
exceeds GitHub's 100 MB per-file limit.

Obtain `data/chroma_db/` separately (scp, USB, or faculty file share) and place it so
the database sits at exactly this path:

```
data/chroma_db/chroma.sqlite3
```

A common mistake after unzipping is one extra folder level
(`data/chroma_db/chroma_db/…`), which makes Chroma silently open an empty database.

Verify before deploying:

```bash
docker compose -p dbp-chatbot run --rm --no-deps chatbot python /app/verify_chroma.py
# Document count : 33320   <- must be exactly this
```

Collection name: `dbp_khidmatnasihat_clean_atomic` · 33,320 documents.

## Repository layout

| Path | Purpose |
|---|---|
| `deploy.sh` | One-command deployment |
| `README_DEPLOY.md` | Full runbook: verification, troubleshooting, security |
| `server-check.sh` | Read-only survey of an unfamiliar target machine |
| `docker-compose.yml` | Two-service definition (`llm`, `chatbot`) |
| `Dockerfile` | Chatbot image. **torch is pinned here, never in `requirements.txt`** |
| `app/ui/app.py` | Streamlit interface |
| `app/scripts/phase4_retrieval_rerank.py` | Retrieval, reranking, selective HyDE |
| `app/scripts/phase5_generation.py` | Prompting and generation against llama.cpp |
| `app/verify_chroma.py` | Knowledge base integrity check |
| `docs/legacy/` | Superseded faculty PDFs, kept as a record |

## A note on dependencies

`torch` is pinned **only** in the `Dockerfile`, installed from the CPU-only index, and
`torchvision`/`torchaudio` are deliberately not installed. Adding `torch` back to
`requirements.txt` reintroduces a version-skew bug that surfaces as a misleading
`cannot import name 'XLMRobertaForMaskedLM'` error, and pulls ~15 CUDA wheels that are
useless on AMD hardware. See the "torch trap" section of `README_DEPLOY.md`.

After changing any pinned version:

```bash
docker exec dbp-chatbot pip check   # must report: No broken requirements found
```
# warisan_project
