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

    def test_dual_index_merge_policy_reads_legacy_and_new(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            legacy_file = tmp / "legacy_only.txt"
            new_file = tmp / "new_only.txt"
            legacy_file.write_text("遗迹线索只在旧库里。", encoding="utf-8")
            new_file.write_text("新设定条目只在新库里。", encoding="utf-8")

            legacy_index = tmp / "legacy" / "text_index.json"
            new_index = tmp / "new" / "text_index.json"

            retrieve_text(
                query="遗迹线索",
                top_k=2,
                config=RetrievalConfig(
                    data_root=tmp / "missing_root",
                    extra_files=(legacy_file,),
                    index_path=legacy_index,
                    rebuild_index=True,
                ),
            )
            retrieve_text(
                query="新设定条目",
                top_k=2,
                config=RetrievalConfig(
                    data_root=tmp / "missing_root",
                    extra_files=(new_file,),
                    index_path=new_index,
                    rebuild_index=True,
                ),
            )

            merged = retrieve_text(
                query="线索 条目",
                top_k=5,
                config=RetrievalConfig(
                    data_root=tmp / "missing_root",
                    legacy_index_path=legacy_index,
                    new_index_path=new_index,
                    rag_policy="merge",
                ),
            )
            sources = {item.get("rag_source") for item in merged["results"]}
            self.assertIn("legacy", sources)
            self.assertIn("new", sources)
            self.assertEqual(merged["stats"]["policy_selected"], "merge")

    def test_dual_index_auto_policy_can_pick_new(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            legacy_file = tmp / "legacy_only.txt"
            new_file = tmp / "new_only.txt"
            legacy_file.write_text("旧世界观条目。", encoding="utf-8")
            new_file.write_text("最新角色设定。", encoding="utf-8")

            legacy_index = tmp / "legacy" / "text_index.json"
            new_index = tmp / "new" / "text_index.json"

            retrieve_text(
                query="旧世界观",
                top_k=2,
                config=RetrievalConfig(
                    data_root=tmp / "missing_root",
                    extra_files=(legacy_file,),
                    index_path=legacy_index,
                    rebuild_index=True,
                ),
            )
            retrieve_text(
                query="最新角色设定",
                top_k=2,
                config=RetrievalConfig(
                    data_root=tmp / "missing_root",
                    extra_files=(new_file,),
                    index_path=new_index,
                    rebuild_index=True,
                ),
            )

            out = retrieve_text(
                query="最新版本应该怎么写",
                top_k=3,
                config=RetrievalConfig(
                    data_root=tmp / "missing_root",
                    legacy_index_path=legacy_index,
                    new_index_path=new_index,
                    rag_policy="auto",
                ),
            )
            self.assertEqual(out["stats"]["policy_selected"], "new")
            self.assertTrue(all(item.get("rag_source") == "new" for item in out["results"]))

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


if __name__ == "__main__":
    unittest.main()
