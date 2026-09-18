from pathlib import Path
import csv
import sys
import tempfile
import unittest


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from api.service import append_feedback, build_chat_response, normalize_question


class ApiContractTests(unittest.TestCase):
    def test_question_validation_rejects_blank_and_oversized_input(self):
        with self.assertRaisesRegex(ValueError, "lengkap"):
            normalize_question("   ")
        with self.assertRaisesRegex(ValueError, "2000"):
            normalize_question("a" * 2001)
        self.assertEqual(normalize_question("  Apakah   maksud kata?  "), "Apakah maksud kata?")

    def test_chat_response_exposes_safe_reasoning_metadata_and_source_previews(self):
        def answerer(question):
            return {
                "answer": "Ialah dan adalah mempunyai fungsi yang berbeza.",
                "top_score": 1.72,
                "used_hyde": True,
                "expanded": True,
                "question_type": "comparison",
                "thinking_mode": "thinking",
                "retrieved_contexts": ["Ialah hadir di hadapan frasa nama. " * 20],
            }

        result = build_chat_response("Beza ialah dan adalah?", answerer)
        self.assertEqual(result["thinking_mode"], "thinking")
        self.assertEqual(result["question_type"], "comparison")
        self.assertTrue(result["used_hyde"])
        self.assertEqual(len(result["sources"]), 1)
        self.assertLessEqual(len(result["sources"][0]["preview"]), 321)
        self.assertNotIn("retrieved_contexts", result)

    def test_empty_model_answer_is_a_service_error(self):
        with self.assertRaisesRegex(RuntimeError, "tidak menghasilkan"):
            build_chat_response("Soalan lengkap", lambda _question: {"answer": ""})

    def test_feedback_is_appended_with_formula_injection_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feedback.csv"
            append_feedback(
                path,
                {
                    "message_id": "m1",
                    "question": "=IMPORTXML('bad')",
                    "answer": "Jawapan",
                    "rating": "helpful",
                    "thinking_mode": "thinking",
                },
            )
            append_feedback(path, {"message_id": "m2", "rating": "unhelpful"})
            with path.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["question"].startswith("'="))
        self.assertEqual(rows[0]["rating"], "helpful")


if __name__ == "__main__":
    unittest.main()
