# DBP Bahasa Melayu Advisory Chatbot — Deployment Guide

**AMD / GMKtec edition (Radeon iGPU, Vulkan backend).** No LM Studio, no ROCm, no CUDA.

---

## Quick start

On a machine that already has Docker:

```bash
cd DBP_Chatbot_Deploy
./deploy.sh
```

That is the whole deployment. The script detects this machine's GPU group IDs,
writes `.env`, pulls and builds the images, starts both containers, verifies the
knowledge base, and prints the URL. It is safe to re-run at any time.

| Command | What it does |
|---|---|
| `./deploy.sh` | Full deploy. Re-runnable. |
| `./deploy.sh check` | Preflight only — changes nothing. Run this first on an unfamiliar machine. |
| `./deploy.sh status` | Show container status |
| `./deploy.sh logs` | Follow logs |
| `./deploy.sh stop` | Stop **only this project** |

---

## Architecture

Two containers on a private Docker network:

```
dbp-chatbot   Streamlit UI + BGE-M3 embeddings + BGE reranker + ChromaDB client   (CPU)
     |
     |  http://llm:8080/v1/   (private network, never published to the LAN)
     v
dbp-llm       llama.cpp Vulkan server + Qwen3 8B (Q5_K_M GGUF)                    (GPU)
```

- Only the Streamlit port is published to the host. The LLM API is deliberately unreachable from outside Docker.
- Retrieval and reranking run on **CPU**; only text generation uses the GPU.
- Knowledge base: `dbp_khidmatnasihat_clean_atomic`, **33,320 documents**, in `data/chroma_db/`.
- Everything runs locally. Nothing is sent to any cloud service. The only outbound traffic is a
  one-time model download on first run (Qwen3 GGUF + BGE weights), afterwards cached in Docker volumes.

---

## Requirements

| | |
|---|---|
| OS | Ubuntu x86_64 (headless server or desktop both work) |
| GPU | AMD Radeon with `amdgpu` driver active — `/dev/dri` and `/dev/kfd` must exist |
| Docker | Docker Engine + `docker compose` plugin |
| Disk | ~14 GB free (3 GB image + build cache + ~5.9 GB model) |
| Network | Access to Docker Hub, ghcr.io and huggingface.co for the first run |

You do **not** need to be in the host `render`/`video` groups. The Compose file grants
those groups inside the container via `group_add`, which is why this works on a shared
server where you cannot change your own account.

No monitor is required. Vulkan compute works headless through `/dev/dri/renderD*`.

---

## Deploying to a new machine

1. Copy the whole `DBP_Chatbot_Deploy` folder across, keeping `data/chroma_db/` intact
   (it must contain `chroma.sqlite3` plus all UUID/HNSW directories).
2. Confirm the layout — `chroma.sqlite3` must be at exactly this depth:
   ```
   DBP_Chatbot_Deploy/data/chroma_db/chroma.sqlite3
   ```
   A common mistake after unzipping is one extra level (`data/chroma_db/chroma_db/…`).
3. Run the preflight:
   ```bash
   ./deploy.sh check
   ```
4. Deploy:
   ```bash
   ./deploy.sh
   ```

### Do not carry `.env` between machines

`RENDER_GID` and `VIDEO_GID` are **machine-specific**. They differ between machines and
between Ubuntu releases, and wrong values are the single most common cause of "the GPU
is not detected" on a new server. `deploy.sh` regenerates them every run:

```bash
getent group render | cut -d: -f3
getent group video  | cut -d: -f3
```

`.env.example` is a template for reference only — it intentionally leaves those two blank.

---

## Verifying the deployment

`deploy.sh` runs these automatically, but you can run them by hand.

**Is the GPU actually being used?** Ask the binary directly:

```bash
docker run --rm --device=/dev/dri --device=/dev/kfd \
  --group-add "$(getent group render | cut -d: -f3)" \
  --group-add "$(getent group video  | cut -d: -f3)" \
  --entrypoint /app/llama-server ghcr.io/ggml-org/llama.cpp:server-vulkan --list-devices
```

Expected — a real GPU, not `llvmpipe`:

```
Available devices:
  Vulkan0: Radeon 8060S Graphics (RADV STRIX_HALO) (97500 MiB, 89168 MiB free)
```

> **Do not use the old log-grep check.** Older guides say to look for
> `ggml_vulkan: Found 1 Vulkan devices` in the `llm` logs. Recent llama.cpp builds
> no longer print that banner at all, so grepping the log reports a GPU failure on a
> machine that is working perfectly. Mesa also reports this chip as `RADV STRIX_HALO`
> on current drivers, not `RADV GFX1151` as older documentation states. Use
> `--list-devices` — it works on every build.

**Knowledge base:**

```bash
docker compose -p dbp-chatbot run --rm --no-deps chatbot python /app/verify_chroma.py
# Document count : 33320   <- must be exactly this
```

If the count is wrong, the data folder is mounted from the wrong path.
**Do not rebuild or re-embed the knowledge base.**

**LLM reachable on the private network:**

```bash
docker run --rm --network dbp-chatbot_dbp-internal curlimages/curl:latest \
  -fsS http://llm:8080/v1/models
```

**Streamlit:**

```bash
curl http://127.0.0.1:18501/_stcore/health   # -> ok
```

---

## Troubleshooting

### "Gagal memuatkan backend" with `cannot import name 'XLMRobertaForMaskedLM'`

**This error message is misleading and has nothing to do with that class.**
`transformers` uses a lazy import loader that swallows the real exception and reports a
generic "cannot import name". The actual failure is almost always a **torch/torchvision
ABI mismatch**. Diagnose it with:

```bash
docker exec dbp-chatbot pip check
```

which reveals the truth:

```
torchvision 0.18.1+cpu has requirement torch==2.3.1, but you have torch 2.8.0
```

**Cause and permanent fix.** The Dockerfile and `requirements.txt` were both pinning
torch. The Dockerfile installed torch 2.3.1 + torchvision 0.18.1 from the CPU index,
then `requirements.txt` installed `torch==2.8.0`, which upgraded torch but left
torchvision compiled against the old ABI. The import chain
`app.py → phase5_generation → phase4_retrieval_rerank → FlagEmbedding → transformers →
image_utils → torchvision` then died.

This is now fixed and must stay fixed:

- **torch is pinned only in the `Dockerfile`**, installed from the CPU-only index.
- **`torch` must NOT be added back to `requirements.txt`.** A bare `torch==2.8.0` there
  resolves to the CUDA build from PyPI, which drags in ~15 `nvidia-*-cu12` wheels that
  are useless on an AMD machine — that alone inflated the image from 3 GB to 13.8 GB.
- **torchvision and torchaudio are deliberately not installed.** This is a text-only RAG
  pipeline that never uses them; they only reintroduce the version-skew trap.

Whenever you change any pinned version, re-check with `docker exec dbp-chatbot pip check`
before considering the deployment good.

### Everything else

| Symptom | Meaning | Action |
|---|---|---|
| `/dev/dri` or `/dev/kfd` missing | `amdgpu` driver not active | Ask faculty IT. **Do not install ROCm** or a custom kernel. |
| `--list-devices` shows only `llvmpipe` | GPU not reachable from Docker | Check `RENDER_GID`/`VIDEO_GID` in `.env`; re-run `./deploy.sh` |
| `--list-devices` shows nothing | Device passthrough failed | Check `devices:` / `group_add:` in `docker-compose.yml` |
| Answers are very slow | Running on CPU fallback | Run the `--list-devices` check above |
| Chroma count is not 33,320 | Wrong data folder mounted | Fix the mount path. Do **not** re-index. |
| Port already in use | Another faculty app holds it | `deploy.sh` picks the next free port automatically |
| Chatbot cannot reach the LLM | LLM still loading, or network issue | `./deploy.sh logs`, then the `/v1/models` check above |
| `pip check` reports conflicts | Dependency skew | See the torch section above |

### Never run these on a shared server

```
docker system prune      docker container prune      docker volume prune
```

They would destroy other faculty applications on the same machine. To remove **only**
this project:

```bash
./deploy.sh stop          # equivalent to: docker compose -p dbp-chatbot down
```

Avoid `down -v` unless you intend to delete the cached Qwen3 model.

---

## Network exposure

By default Docker publishes the Streamlit port on `0.0.0.0`, so the chatbot is reachable
from the whole faculty LAN at `http://<server-ip>:18501`, not just from the server itself.

For a first installation, prefer an SSH tunnel from your own laptop:

```bash
ssh -L 18501:localhost:18501 your_username@faculty-server-ip
# then open http://localhost:18501 on your laptop
```

To bind to localhost only, edit `docker-compose.yml`:

```yaml
ports:
  - "127.0.0.1:${CHATBOT_HOST_PORT}:8501"
```

Before giving an external party a URL: put it behind HTTPS and access control, keep the
llama.cpp port unpublished, and confirm firewall changes with faculty IT.

---

## Smoke test before declaring success

1. Chroma count is exactly 33,320
2. `--list-devices` shows the Radeon, not `llvmpipe`
3. Streamlit health returns `ok`
4. Three known-answerable DBP questions return sensible Malay answers
5. One insufficient-context question triggers the refusal path
6. One out-of-domain question is refused rather than answered from a weak match
7. A feedback rating appends a row to `data_eval/user_feedback.csv`

> Step 6 is worth real attention. A question whose topic is absent from the knowledge base
> can still return the nearest-neighbour chunk and be answered confidently from it, rather
> than being refused. Check that the relevance threshold behaves as your thesis expects.

---

## File reference

| File | Purpose |
|---|---|
| `deploy.sh` | One-command deployment. Start here. |
| `docker-compose.yml` | Two-service definition (`llm`, `chatbot`) |
| `Dockerfile` | Chatbot image. **torch is pinned here, not in requirements.txt** |
| `requirements.txt` | Python deps. Deliberately contains no `torch` line |
| `.env` | Generated per-machine by `deploy.sh` — do not copy between servers |
| `.env.example` | Reference template only |
| `app/ui/app.py` | Streamlit interface |
| `app/scripts/phase4_retrieval_rerank.py` | Retrieval + reranking + HyDE |
| `app/scripts/phase5_generation.py` | Prompting and generation against llama.cpp |
| `app/verify_chroma.py` | Knowledge base integrity check |
| `data/chroma_db/` | The 33,320-document knowledge base |
| `*.bak-nvidia` | Superseded NVIDIA/LM Studio-era files, kept for reference |
