from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigurationTests(unittest.TestCase):
    def test_qwen3_model_is_consistent_across_deployment_files(self):
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        deploy = (ROOT / "deploy.sh").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for content in (env_example, deploy):
            self.assertIn("LMSTUDIO_MODEL=Qwen/Qwen3-8B", content)
            self.assertIn("LLAMA_HF_REPO=Qwen/Qwen3-8B-GGUF:Q5_K_M", content)
            self.assertIn("RAG_K_SMALL=15", content)
            self.assertIn("RAG_K_LARGE=40", content)
            self.assertIn("RAG_FINAL_N=6", content)
        self.assertIn("Qwen3 8B (Q5_K_M GGUF)", readme)

    def test_llama_context_window_supports_multi_chunk_reasoning(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("--ctx-size 8192", compose)


if __name__ == "__main__":
    unittest.main()
