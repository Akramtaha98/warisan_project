"""Live smoke test for the deployed DBP retrieval and Qwen3 reasoning path."""

from __future__ import annotations

from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from phase5_generation import NOT_FOUND, answer_question


QUESTION = "Apakah perbezaan antara 'ialah' dengan 'adalah'?"


def main() -> None:
    result = answer_question(QUESTION)
    answer = (result.get("answer") or "").strip()
    debug = result.get("debug") or {}
    contexts = result.get("retrieved_contexts") or []

    if not answer or answer == NOT_FOUND:
        raise SystemExit("LIVE SMOKE FAILED: comparison question was not answered.")
    if "<think>" in answer.lower() or "</think>" in answer.lower():
        raise SystemExit("LIVE SMOKE FAILED: private reasoning leaked into the answer.")
    if debug.get("question_type") != "comparison":
        raise SystemExit("LIVE SMOKE FAILED: comparison intent was not detected.")
    if debug.get("thinking_mode") != "thinking":
        raise SystemExit("LIVE SMOKE FAILED: Qwen3 thinking mode was not selected.")
    if not contexts:
        raise SystemExit("LIVE SMOKE FAILED: the answer has no retrieved DBP context.")

    print("LIVE REASONING SMOKE PASSED")
    print(f"top_score={debug.get('top_score')}")
    print(f"contexts={len(contexts)}")
    print(f"answer_preview={answer[:180]}")


if __name__ == "__main__":
    main()
