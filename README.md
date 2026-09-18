# Warisan DBP Chatbot

A local Retrieval-Augmented Generation (RAG) assistant for Bahasa Melayu language
advice. It retrieves evidence from Dewan Bahasa dan Pustaka's Khidmat Nasihat Bahasa
collection, reranks the results, and asks Qwen3 to produce a grounded Malay answer.

The project is designed as an academic prototype that is practical to deploy on one
AMD machine. The model API stays inside Docker, the knowledge base stays on the host,
and no question is sent to a hosted AI service.

---

## What it does

| Capability | Implementation |
|---|---|
| Malay language questions | Definitions, spelling, terminology, usage, grammar, comparisons, corrections, and multi-part questions |
| Grounded answers | Answers are limited to retrieved DBP evidence |
| Semantic search | BGE-M3 dense embeddings over a 33,320-document ChromaDB collection |
| Candidate ranking | BGE Reranker v2 M3 |
| Weak-query recovery | Adaptive retrieval and query-specific HyDE |
| Answer generation | Qwen3 8B (Q5_K_M GGUF) through llama.cpp |
| Selective reasoning | Complex questions use `/think`; direct questions use `/no_think` |
| Local interface | Streamlit chat UI with feedback and optional technical details |

This is a **DBP language-advisory assistant**, not a general-purpose knowledge bot.
Qwen3 improves Malay generation and reasoning, but it is not allowed to invent an
answer when the DBP collection does not support one.

---

## Architecture

### Request flow

```text
User question
    │
    ├─ detect question type
    │
    ├─ retrieve 15 candidates with BGE-M3
    │      └─ expand to 40 when confidence or coverage is weak
    │
    ├─ rerank candidates with BGE Reranker v2 M3
    │      └─ use query-specific HyDE when expanded retrieval is still weak
    │
    ├─ select up to 6 grounded context chunks
    │
    └─ Qwen3 answer
           ├─ /no_think  definitions and direct questions
           └─ /think     comparisons, grammar, corrections, multi-part questions
```

### Runtime layout

```text
dbp-chatbot   Streamlit + retrieval + reranking + ChromaDB client              CPU
     │
     │  http://llm:8080/v1/  private Docker network
     ▼
dbp-llm       llama.cpp Vulkan server + Qwen3 8B (Q5_K_M GGUF)                 GPU
```

Only the Streamlit port is published. The llama.cpp API is not exposed to the LAN.
The target machine is an AMD Radeon system using Vulkan; ROCm and CUDA are not used.

---

## Repository layout

```text
warisan_project/
├── app/
│   ├── scripts/
│   │   ├── phase4_retrieval_rerank.py   # retrieval, reranking, expansion, HyDE
│   │   └── phase5_generation.py         # intent routing and grounded generation
│   ├── ui/app.py                        # Streamlit interface
│   ├── smoke_live.py                    # deployed reasoning smoke test
│   └── verify_chroma.py                 # knowledge-base integrity check
├── data/chroma_db/                      # external knowledge base; git-ignored
├── data_eval/                           # runtime feedback data
├── tests/                               # fast regression suite
├── .env.example                         # documented runtime configuration
├── Dockerfile                           # chatbot image
├── docker-compose.yml                   # chatbot + private LLM service
├── deploy.sh                            # deployment and lifecycle commands
├── smoke-test.sh                        # offline and live verification
└── README_DEPLOY.md                     # detailed deployment runbook
```

---

## Requirements

| Requirement | Notes |
|---|---|
| Operating system | Ubuntu x86_64 is the deployment target |
| Container runtime | Docker Engine with the `docker compose` plugin |
| GPU | AMD Radeon with `/dev/dri` and `/dev/kfd` available |
| Free disk | At least 14 GB for images, Qwen3, BGE models, and build cache |
| Knowledge base | `data/chroma_db/chroma.sqlite3`, supplied separately |
| Network | Required only for the initial image and model downloads |

Tested target hardware: GMKtec EVO-X2 with Ryzen AI Max+ 395 / Radeon 8060S.

---

## Getting it running

### 1. Clone the repository

```bash
git clone https://github.com/Akramtaha98/warisan_project.git
cd warisan_project
```

### 2. Add the DBP knowledge base

The ChromaDB collection is approximately 676 MB and is not stored in GitHub.
Copy it into the repository so the SQLite file is at exactly:

```text
data/chroma_db/chroma.sqlite3
```

Do not leave an extra nested directory such as
`data/chroma_db/chroma_db/chroma.sqlite3`.

The expected collection is:

```text
name:      dbp_khidmatnasihat_clean_atomic
documents: 33320
```

### 3. Check the target machine

```bash
./deploy.sh check
```

This verifies Docker, AMD device nodes, disk space, required project files, and the
knowledge-base path without changing the machine.

### 4. Deploy

```bash
./deploy.sh
```

The script:

1. Detects the machine-specific `render` and `video` group IDs.
2. Generates `.env` from the detected host configuration.
3. Pulls the llama.cpp Vulkan image.
4. Downloads and starts Qwen3 8B Q5 on first use.
5. Builds the chatbot image.
6. Verifies that ChromaDB contains exactly 33,320 documents.
7. Starts Streamlit and prints the local URL.

The first deployment downloads roughly 5.9 GB of Qwen3 weights plus the BGE model
files. Later starts reuse Docker volumes and the Hugging Face cache.

### 5. Verify the deployed reasoning path

```bash
./smoke-test.sh --live
```

The live smoke test asks a DBP comparison question and requires all of the following:

- ChromaDB returns supporting context.
- The question is classified as a comparison.
- Qwen3 thinking mode is selected.
- A non-refusal answer is generated.
- Private `<think>` content is not exposed.

---

## Daily commands

| Command | Purpose |
|---|---|
| `./deploy.sh` | Build, configure, verify, and start the full project |
| `./deploy.sh check` | Run read-only deployment preflight checks |
| `./deploy.sh status` | Show project container status |
| `./deploy.sh logs` | Follow chatbot and model logs |
| `./deploy.sh stop` | Stop this project without deleting cached models |
| `./smoke-test.sh` | Run source, configuration, and regression checks |
| `./smoke-test.sh --live` | Exercise the deployed DBP + Qwen3 reasoning path |

For detailed troubleshooting and server verification, see
[`README_DEPLOY.md`](README_DEPLOY.md).

---

## Answer-quality design

### Adaptive retrieval

The first pass retrieves 15 candidates. Retrieval expands to 40 when the top score is
below the expansion threshold or fewer than six usable chunks remain. The reranker
then selects at most six chunks for generation.

The defaults are:

| Setting | Default | Meaning |
|---|---:|---|
| `RAG_K_SMALL` | `15` | Initial dense candidates |
| `RAG_K_LARGE` | `40` | Expanded dense candidates |
| `RAG_FINAL_N` | `6` | Maximum context chunks |
| `RAG_MIN_KEEP_SCORE` | `0.8` | Minimum reranker score retained |
| `RAG_EXPAND_SCORE` | `1.5` | Expand below this score |
| `RAG_HYDE_SCORE` | `1.0` | Consider HyDE below this score |
| `RAG_ANSWER_SCORE` | `0.8` | Refuse below this final score |

These scores are reranker-specific values, not percentages. Calibrate them against a
labelled Malay evaluation set before changing production defaults.

### Query-specific HyDE

HyDE generates a short hypothetical DBP-style passage about the user's actual
question. It is accepted only when it retains meaningful terms from that question.
An unrelated generated passage is discarded, and the original retrieval result is
kept.

### Selective thinking

| Question type | Qwen mode |
|---|---|
| Definition, spelling, terminology, usage, yes/no | `/no_think` |
| Comparison, grammar analysis, sentence correction, multi-part | `/think` |

Thinking is internal. The application removes `<think>...</think>` content and fails
safely if the model produces reasoning without a final answer.

### Grounding rules

The system prompt is intentionally compact. It requires the model to:

- answer in formal, natural Bahasa Melayu;
- use only facts supported by retrieved context;
- combine evidence for comparison and multi-part questions;
- state the limit when evidence is partial;
- refuse when relevant evidence is absent;
- never expose metadata, document IDs, retrieval details, or internal reasoning;
- never invent examples.

ChromaDB failures are reported clearly. The application does not silently replace
semantic retrieval with low-quality SQL substring matching.

---

## Configuration

`deploy.sh` generates `.env` for the target machine. Use [`.env.example`](.env.example)
as documentation, but do not copy GPU group IDs between hosts.

Important variables:

| Variable | Purpose |
|---|---|
| `CHROMA_PERSIST_DIR` | ChromaDB directory inside the chatbot container |
| `CHROMA_COLLECTION_NAME` | DBP collection name |
| `LMSTUDIO_BASE_URL` | Historical name for the private llama.cpp API URL |
| `LMSTUDIO_MODEL` | Model identifier sent to the OpenAI-compatible API |
| `LLAMA_HF_REPO` | Hugging Face GGUF repository and quantization |
| `RAG_DEVICE` | Device used for embeddings and reranking; defaults to CPU |
| `CHATBOT_HOST_PORT` | Streamlit port published on the host |
| `RENDER_GID`, `VIDEO_GID` | Host-specific AMD device group IDs |

The `LMSTUDIO_*` names remain for compatibility with the application code. LM Studio
is not part of the Docker architecture.

---

## Testing

Run the fast smoke test before committing or deploying:

```bash
./smoke-test.sh
```

It checks Python compilation, deployment script syntax, Qwen3 configuration, adaptive
retrieval, HyDE relevance, resource caching, intent routing, and private-reasoning
removal.

To run the regression suite directly:

```bash
python3 -m unittest discover -s tests -v
```

After changing a pinned dependency, also verify the built image:

```bash
docker exec dbp-chatbot pip check
```

Expected result: `No broken requirements found.`

---

## Dependency note

PyTorch is pinned only in the [`Dockerfile`](Dockerfile) and is installed from the
CPU-only package index. Do not add a second PyTorch pin to `requirements.txt`.

The chatbot performs only text retrieval and generation, so `torchvision` and
`torchaudio` are intentionally absent. Adding them can introduce incompatible ABI
versions and unnecessary CUDA packages on an AMD deployment.

---

## Known limitations

- The 676 MB ChromaDB collection must be transferred separately.
- The first deployment needs internet access to download container images and models.
- Current retrieval is dense BGE-M3 retrieval followed by reranking; a separate sparse
  BM25 index is not yet included.
- Threshold defaults have regression coverage but still require calibration on a
  larger labelled DBP evaluation set.
- The project answers DBP language-advisory questions only. General history, science,
  politics, prices, and current affairs require a separate knowledge source or mode.

---

## Further documentation

- [`README_DEPLOY.md`](README_DEPLOY.md) — full deployment and troubleshooting guide
- [`docs/legacy/`](docs/legacy/) — superseded deployment documents retained for reference

Everything needed to build the application is versioned here. Model weights, the DBP
knowledge base, generated `.env`, caches, and runtime feedback remain outside Git.
