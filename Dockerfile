FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git build-essential \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch. Qwen3 runs on the Radeon 8060S via the llama.cpp Vulkan container,
# so this image never needs a GPU build of torch. torch is pinned HERE and deliberately
# left out of requirements.txt: when both pinned it, requirements.txt upgraded torch to
# 2.8.0 while torchvision/torchaudio stayed on the 2.3.1 ABI, which broke every
# transformers model import. torchvision/torchaudio are not installed at all -- this is
# a text-only RAG pipeline, and they only add a version-skew trap plus ~2 GB.
RUN pip install --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple \
    torch==2.8.0 "typing_extensions==4.12.2"

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY app /app
COPY .streamlit /root/.streamlit

RUN mkdir -p /app/data/chroma_db /app/data_eval

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
  CMD curl -f http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "ui/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
