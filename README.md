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
| Local interface | Responsive React UI with source previews, English translation, feedback memory, and system status |

This is a **DBP language-advisory assistant**, not a general-purpose knowledge bot.
Qwen3 improves Malay generation and reasoning, but it is not allowed to invent an
answer when the DBP collection does not support one.

### Feedback learning

The useful/not-useful controls form a transparent, per-user feedback loop:

- A **useful** rating saves the answer as a preferred example for similar questions.
- A **not useful** rating opens a correction box. The correction is supplied to Qwen3
  on related future questions and can be reused for an exact match during an API outage.
- Relevant feedback is labelled in the answer metadata when it is used.

This is feedback memory, not instant retraining of the Qwen3 model. On the Vercel demo,
the memory stays in that user's browser and is not shared with other users. The lab-PC
deployment also writes feedback to `data_eval/user_feedback.csv`, which can later be
reviewed and converted into a curated fine-tuning or evaluation dataset.

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
dbp-chatbot   React UI + FastAPI + retrieval + reranking + ChromaDB            CPU
     │
     │  http://llm:8080/v1/  private Docker network
     ▼
dbp-llm       llama.cpp Vulkan server + Qwen3 8B (Q5_K_M GGUF)                 GPU
```

Only the web application port is published. The llama.cpp API is not exposed to the LAN.
The target machine is an AMD Radeon system using Vulkan; ROCm and CUDA are not used.

---

## Repository layout

```text
warisan_project/
├── app/
│   ├── scripts/
│   │   ├── phase4_retrieval_rerank.py   # retrieval, reranking, expansion, HyDE
│   │   └── phase5_generation.py         # intent routing and grounded generation
│   ├── api/main.py                      # FastAPI routes and React static serving
│   ├── api/service.py                   # framework-independent API behavior
│   ├── smoke_live.py                    # deployed reasoning smoke test
│   └── verify_chroma.py                 # knowledge-base integrity check
├── frontend/                            # React/Vite application and UI tests
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
| Network | Required initially for images, Python/React packages, and model downloads |

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

### Optional Malay QA sample database

For development on a computer that does not have the full DBP collection, the
repository includes 100 synthetic Malay question-and-answer records in
`app/sample_data/malay_qa.json`. They cover spelling, grammar, punctuation,
affixes, sentence structure, usage, correction and multi-rule reasoning. The
records are test fixtures, not official DBP advice and not a replacement for
the production knowledge base.

Build the isolated sample with the same BGE-M3 embedding model used by the
chatbot. If the chatbot image has not been built yet, build it first:

```bash
docker build -t dbp-chatbot:1.0 .
mkdir -p data/sample_chroma_db
docker run --rm \
  -v "$PWD/data/sample_chroma_db:/app/data/sample_chroma_db" \
  -v dbp-chatbot_huggingface-cache:/root/.cache/huggingface \
  dbp-chatbot:1.0 \
  python /app/build_sample_chroma.py \
    --output /app/data/sample_chroma_db
```

The command creates the collection `dbp_malay_qa_sample` under
`data/sample_chroma_db/` and verifies that every source record was inserted.
To rebuild that sample deliberately, append `--replace`. The builder refuses to
write to `data/chroma_db` or use the production collection name.

After the normal deployment has configured `.env` and started Qwen3, switch only
the chatbot container to the sample collection:

```bash
docker compose -p dbp-chatbot \
  -f docker-compose.yml \
  -f docker-compose.sample.yml \
  up -d --force-recreate chatbot

curl http://127.0.0.1:18501/api/health
```

You can then ask questions such as `Apakah perbezaan antara ialah dengan
adalah?` in the web interface. Restore the full production collection by
running `./deploy.sh` again. The sample override mounts its database read-only.

When all Python dependencies are already installed locally, the equivalent
command is:

```bash
python3 app/build_sample_chroma.py
```

The generated Chroma files are ignored by Git because they can be reproduced
from the small, reviewed JSON fixture. Keep the complete production ChromaDB at
`data/chroma_db/` as described above.

### Public Vercel demo with hosted Qwen3

The repository also contains a lightweight public-demo path for Vercel. It uses
the 100 reviewed synthetic QA records for serverless retrieval and calls Qwen3
through OpenRouter when `OPENROUTER_API_KEY` is configured, with Vercel AI
Gateway as the alternative provider. Qwen3 generates the answer and performs a
separate quality assessment. This mode does not upload the production ChromaDB
or local model files.

The demo routes direct questions through `/no_think` for concise answers. It
routes comparison, correction, multi-part and other difficult questions through
`/think`, retrieves up to six supporting QA records, and removes private
reasoning tokens before returning the final answer.

Users can also enable **Fikir mendalam** beside the message box. This explicitly
forces `/think` mode and six-reference retrieval for the next question, including
questions that would normally use the direct route. While waiting, the interface
shows safe progress stages for understanding, retrieval, comparison and answer
verification. These stages explain the workflow without exposing private model
chain-of-thought.

The displayed quality score is between 0 and 100 and combines Qwen3's assessment
of grounding, relevance, completeness and Malay-language quality. It is useful
for testing, but it is a model-generated estimate rather than an official DBP or
human evaluation.

If the hosted Qwen3 service is rate-limited, unavailable, not configured or too
slow, the public demo automatically returns a clearly labelled **Jawapan dataset**
from the closest matching local QA record. Greetings are also handled locally.
This fallback keeps the website usable without sending the question to another
unapproved provider; it does not pretend that the fallback answer came from Qwen3.

Each completed answer also includes a **Translate to English** button. Translation
is requested only when the user clicks it, uses the same configured Qwen provider,
keeps the original Malay answer visible, and can be shown or hidden below it. If
Qwen is unavailable, a clearly labelled basic local translation keeps the button
usable without sending the answer to another provider.

Deploy from the repository root:

```bash
npx vercel
npx vercel --prod
```

For the free OpenRouter test path, add `OPENROUTER_API_KEY` in the Vercel project
environment. Vercel deployments can alternatively authenticate AI Gateway
through the deployment's OIDC token or an `AI_GATEWAY_API_KEY`. Optionally set
`QWEN_MODEL` to another model supported by the selected provider.

The Vercel demo supports up to six recent user/assistant messages so short
follow-ups such as `contoh pula?` can be interpreted using the current
conversation. It also applies a small per-instance request limit for test use.

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
7. Starts the React/FastAPI application and prints the local URL.

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
| Any question with **Fikir mendalam** enabled | `/think` with six references |

Thinking is internal. The application removes `<think>...</think>` content and fails
safely if the model produces reasoning without a final answer. The visible progress
panel reports verifiable processing stages, not hidden chain-of-thought tokens.

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
| `CHATBOT_HOST_PORT` | React/FastAPI port published on the host |
| `RENDER_GID`, `VIDEO_GID` | Host-specific AMD device group IDs |

The `LMSTUDIO_*` names remain for compatibility with the application code. LM Studio
is not part of the Docker architecture.

---

## Testing

Run the fast smoke test before committing or deploying:

```bash
./smoke-test.sh
```

It checks the React production build, frontend API behavior, Python compilation,
deployment syntax, Qwen3 configuration, adaptive retrieval, HyDE relevance, resource
caching, intent routing, feedback safety, and private-reasoning removal.

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
