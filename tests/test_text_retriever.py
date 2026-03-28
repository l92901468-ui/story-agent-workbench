import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from story_agent_workbench.retrieval.text_retriever import (
    RetrievalConfig,
    _pre_chunk_user_text,
    retrieve_text,
)


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

    def test_pre_chunk_user_file_uses_5000_chars(self) -> None:
        text = "a" * 12050
        chunks = _pre_chunk_user_text(text)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(len(chunks[0]), 5000)
        self.assertEqual(len(chunks[1]), 5000)
        self.assertEqual(len(chunks[2]), 2050)

    @patch("story_agent_workbench.retrieval.text_retriever._llm_refine_upload_chunks")
    def test_retrieve_with_ad_hoc_file_uses_llm_refined_segments(self, mock_refine) -> None:
        with TemporaryDirectory() as tmpdir:
            ad_hoc = Path(tmpdir) / "demo_test_file.txt"
            ad_hoc.write_text("第一段。\n第二段。\n第三段。", encoding="utf-8")
            index_path = Path(tmpdir) / "index" / "text_index.json"
            mock_refine.return_value = ["第一段。第二段。", "第三段。"]

            result = retrieve_text(
                query="第三段",
                top_k=2,
                config=RetrievalConfig(
                    data_root=Path(tmpdir) / "missing_root",
                    extra_files=(ad_hoc,),
                    index_path=index_path,
                    rebuild_index=True,
                ),
            )

            self.assertTrue(any("#seg_" in item["source"] for item in result["results"]))
            self.assertEqual(result["stats"]["upload_pre_chunk_size"], 5000)

    def test_project_mode_includes_draft_assets_in_rag_sources(self) -> None:
        with TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir) / "projects" / "p1"
            (project_root / "canon").mkdir(parents=True, exist_ok=True)
            (project_root / "workbench" / "draft" / "open_questions").mkdir(parents=True, exist_ok=True)
            (project_root / "canon" / "chapter.md").write_text("罗安在港口调查。", encoding="utf-8")
            (project_root / "workbench" / "draft" / "open_questions" / "q1.json").write_text(
                '{"title":"主角待确认","summary":"主角可能是艾琳","source_query":"主角是谁"}',
                encoding="utf-8",
            )

            result = retrieve_text(
                query="主角",
                top_k=3,
                config=RetrievalConfig(
                    project_root=project_root,
                    projects_root=project_root.parent,
                    rebuild_index=True,
                ),
            )
            self.assertTrue(any("draft_asset::" in item["source"] for item in result["results"]))
            self.assertGreaterEqual(result["stats"]["total_chunks"], 1)


if __name__ == "__main__":
    unittest.main()
