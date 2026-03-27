import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from story_agent_workbench.retrieval.text_retriever import RetrievalConfig, retrieve_text


class TestTextRetriever(unittest.TestCase):
    def test_retrieve_top_k_and_fields(self) -> None:
        result = retrieve_text(query="灰塔 线索", top_k=2, config=RetrievalConfig())
        self.assertIn("results", result)
        self.assertLessEqual(len(result["results"]), 2)
        self.assertGreaterEqual(len(result["results"]), 1)
        item = result["results"][0]
        for field in ("source", "chunk_id", "layer", "text", "score"):
            self.assertIn(field, item)

    def test_retrieve_with_ad_hoc_test_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            ad_hoc = Path(tmpdir) / "demo_test_file.txt"
            ad_hoc.write_text("这是临时测试文件，用于RAG切块检索。灰塔线索在这里。", encoding="utf-8")
            index_path = Path(tmpdir) / "index" / "text_index.json"

            result = retrieve_text(
                query="灰塔 线索",
                top_k=2,
                config=RetrievalConfig(
                    data_root=Path(tmpdir) / "missing_root",
                    extra_files=(ad_hoc,),
                    index_path=index_path,
                    rebuild_index=True,
                ),
            )

            self.assertGreaterEqual(len(result["results"]), 1)
            self.assertEqual(result["results"][0]["layer"], "test_input")
            stats = result.get("stats", {})
            self.assertEqual(stats.get("extra_files_requested"), 1)
            self.assertEqual(stats.get("extra_files_loaded"), 1)
            self.assertEqual(stats.get("extra_files_skipped"), 0)
            self.assertTrue(index_path.exists())

            result_second = retrieve_text(
                query="灰塔 线索",
                top_k=1,
                config=RetrievalConfig(data_root=Path(tmpdir) / "missing_root", index_path=index_path),
            )
            self.assertGreaterEqual(len(result_second["results"]), 1)
            self.assertGreaterEqual(result_second["stats"].get("index_chunks_updated", 0), 0)


if __name__ == "__main__":
    unittest.main()
