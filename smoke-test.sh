#!/usr/bin/env bash
# Fast project smoke test.
#
#   ./smoke-test.sh          source, configuration and regression checks
#   ./smoke-test.sh --live   also query the deployed ChromaDB + Qwen3 pipeline

set -euo pipefail
cd "$(dirname "$0")"

mode="${1:-offline}"
if [ "$mode" != "offline" ] && [ "$mode" != "--live" ]; then
  echo "Usage: ./smoke-test.sh [--live]" >&2
  exit 2
fi

echo "[1/5] Checking Python source"
python3 -m compileall -q app tests

echo "[2/5] Checking deployment script"
bash -n deploy.sh

echo "[3/5] Verifying the React application"
npm --prefix frontend run verify

echo "[4/5] Running API and reasoning regressions"
python3 -m unittest discover -s tests -v

echo "[5/5] Checking generated deployment configuration"
python3 -m unittest tests.test_deployment_config -v

if [ "$mode" = "--live" ]; then
  echo "[live 1/4] Checking prerequisites"
  command -v docker >/dev/null 2>&1 || {
    echo "LIVE SMOKE FAILED: Docker is not installed." >&2
    exit 1
  }
  [ -f data/chroma_db/chroma.sqlite3 ] || {
    echo "LIVE SMOKE FAILED: data/chroma_db/chroma.sqlite3 is missing." >&2
    exit 1
  }

  echo "[live 2/4] Checking running containers"
  docker inspect -f '{{.State.Running}}' dbp-llm | grep -qx true || {
    echo "LIVE SMOKE FAILED: dbp-llm is not running. Run ./deploy.sh first." >&2
    exit 1
  }
  docker inspect -f '{{.State.Running}}' dbp-chatbot | grep -qx true || {
    echo "LIVE SMOKE FAILED: dbp-chatbot is not running. Run ./deploy.sh first." >&2
    exit 1
  }

  echo "[live 3/4] Checking knowledge base"
  docker exec dbp-chatbot python /app/verify_chroma.py

  echo "[live 4/4] Asking a reasoning smoke question"
  docker exec dbp-chatbot python /app/smoke_live.py
fi

echo "SMOKE TEST PASSED (${mode#--})"
