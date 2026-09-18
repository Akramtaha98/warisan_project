from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


SCRIPTS = Path(__file__).resolve().parents[1] / "app" / "scripts"
sys.path.insert(0, str(SCRIPTS))

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.RequestException = Exception
    requests_stub.post = MagicMock()
    sys.modules["requests"] = requests_stub

import phase5_generation as generation


class GenerationQualityTests(unittest.TestCase):
    def test_comparison_with_supported_context_reaches_model_without_magic_words(self):
        chunks = [
            {"id": "1", "document": "Ialah hadir di hadapan frasa nama.", "metadata": {}},
            {"id": "2", "document": "Adalah hadir di hadapan frasa adjektif.", "metadata": {}},
        ]
        debug = {"top_score": 1.2, "expanded": True, "used_hyde": False}
        with patch.object(generation, "phase4_get_context_chunks", return_value=(chunks, debug)), patch.object(
            generation, "call_lmstudio", return_value="Ialah dan adalah mempunyai fungsi yang berlainan."
        ) as call:
            result = generation.generate_answer(
                "Apakah perbezaan antara ialah dengan adalah?"
            )
        self.assertNotEqual(result["answer"], generation.NOT_FOUND)
        self.assertEqual(result["debug"]["question_type"], "comparison")
        self.assertEqual(result["debug"]["thinking_mode"], "thinking")
        call.assert_called_once()

    def test_complex_question_uses_thinking_but_hides_private_reasoning(self):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {"message": {"content": "<think>analisis rahsia</think>Jawapan yang disokong."}}
            ]
        }
        with patch.object(generation.requests, "post", return_value=response) as post:
            answer = generation.call_lmstudio("prompt", "comparison")
        payload = post.call_args.kwargs["json"]
        self.assertIn("/think", payload["messages"][0]["content"])
        self.assertEqual(answer, "Jawapan yang disokong.")
        self.assertNotIn("analisis rahsia", answer)
        self.assertEqual(generation._strip_private_reasoning("<think>belum selesai"), "")

    def test_simple_definition_uses_direct_mode(self):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "Jawapan ringkas."}}]
        }
        with patch.object(generation.requests, "post", return_value=response) as post:
            generation.call_lmstudio("prompt", "definition")
        self.assertIn("/no_think", post.call_args.kwargs["json"]["messages"][0]["content"])

    def test_intent_classifier_covers_usage_correction_and_multi_part(self):
        self.assertEqual(
            generation.detect_question_type("Bagaimanakah perkataan ini digunakan?"), "usage"
        )
        self.assertEqual(generation.detect_question_type("Tolong betulkan ayat ini"), "correction")
        self.assertEqual(
            generation.detect_question_type("Apakah maksudnya? Berikan contoh?"), "multi_part"
        )


if __name__ == "__main__":
    unittest.main()
