import json
import tempfile
import unittest
from pathlib import Path

from story_agent_workbench.ingest import import_project_folder
from story_agent_workbench.retrieval.text_retriever import RetrievalConfig, retrieve_text


class TestFolderImport(unittest.TestCase):
    def test_folder_import_creates_layout_and_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "demo"
            (project / "incoming").mkdir(parents=True, exist_ok=True)
            (project / "incoming" / "setting_note.md").write_text(
                "# 世界观设定\n\n这是正式设定章节。",
                encoding="utf-8",
            )
            (project / "incoming" / "brainstorm.txt").write_text(
                "脑暴记录：这个桥段待定，需要后续再确认。",
                encoding="utf-8",
            )
            (project / "canon").mkdir(parents=True, exist_ok=True)
            (project / "canon" / "chapter_01.md").write_text("# 第一章\n\n艾琳在港口调查。", encoding="utf-8")
            (project / ".workbench" / "logs").mkdir(parents=True, exist_ok=True)
            (project / ".workbench" / "logs" / "old.txt").write_text("ignore me", encoding="utf-8")

            report = import_project_folder(project)

            self.assertTrue((project / ".workbench" / "chunks" / "chunks.jsonl").exists())
            self.assertTrue((project / ".workbench" / "summaries" / "import_summaries.json").exists())
            self.assertTrue((project / ".workbench" / "graph" / "registry_seed.json").exists())
            self.assertTrue((project / ".workbench" / "logs" / "import_report.json").exists())

            self.assertEqual(report["scanned_files"], 3)
            self.assertEqual(report["auto_classified_files"], 2)
            self.assertEqual(report["incoming_copied_to_layers"], 2)
            self.assertFalse(any("old.txt" in item for item in report["skipped_files"]))

            docs = report["documents"]
            setting_doc = next(d for d in docs if d["source"].endswith("setting_note.md"))
            brainstorm_doc = next(d for d in docs if d["source"].endswith("brainstorm.txt"))
            self.assertEqual(setting_doc["target_layer"], "canon")
            self.assertEqual(setting_doc["classified_by"], "auto")
            self.assertEqual(brainstorm_doc["target_layer"], "draft")
            self.assertIn("keywords", setting_doc["reason"])

    def test_retriever_uses_workbench_chunks_under_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "demo2"
            (project / "incoming").mkdir(parents=True, exist_ok=True)
            (project / "incoming" / "ref.md").write_text("参考资料：灰塔阵营资料整理。", encoding="utf-8")
            import_project_folder(project)

            result = retrieve_text(
                query="灰塔阵营",
                top_k=2,
                config=RetrievalConfig(project_root=project),
            )
            self.assertGreaterEqual(len(result["results"]), 1)
            self.assertIn("incoming/ref.md", result["results"][0]["source"])

            chunk_lines = (project / ".workbench" / "chunks" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
            one = json.loads(chunk_lines[0])
            self.assertIn("chunk_strategy", one)


if __name__ == "__main__":
    unittest.main()
