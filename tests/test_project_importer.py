import json
import tempfile
import unittest
from pathlib import Path

from story_agent_workbench.graph.graph_retriever import GraphConfig, retrieve_graph
from story_agent_workbench.ingest.project_importer import import_project_documents
from story_agent_workbench.retrieval.text_retriever import RetrievalConfig, retrieve_text


class TestProjectImporter(unittest.TestCase):
    def test_import_manifest_and_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_root = Path(tmpdir) / "projects"
            project = projects_root / "p1"
            (project / "canon").mkdir(parents=True, exist_ok=True)
            (project / "draft").mkdir(parents=True, exist_ok=True)
            (project / "reference").mkdir(parents=True, exist_ok=True)

            text = "characters: 艾琳, 罗安\n\ntimeline: 第三夜\n\n剧情推进。"
            (project / "canon" / "chapter_01.md").write_text(text, encoding="utf-8")
            (project / "draft" / "chapter_01.md").write_text("短", encoding="utf-8")
            (project / "reference" / "note.txt").write_text(text, encoding="utf-8")

            report = import_project_documents(project_id="p1", projects_root=projects_root)
            self.assertEqual(report["project_id"], "p1")
            self.assertEqual(report["stats"]["total_docs"], 3)
            self.assertTrue((project / "workbench" / "import_manifest.json").exists())
            self.assertGreaterEqual(len(report["checks"]["duplicate_filenames"]), 1)
            self.assertGreaterEqual(len(report["checks"]["duplicate_content"]), 1)
            self.assertGreaterEqual(len(report["checks"]["too_short"]), 1)

    def test_retriever_and_graph_can_use_project_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            projects_root = Path(tmpdir) / "projects"
            project = projects_root / "p2"
            (project / "canon").mkdir(parents=True, exist_ok=True)
            (project / "workbench" / "extracted").mkdir(parents=True, exist_ok=True)
            (project / "canon" / "chapter_02.md").write_text("艾琳在港口调查灰塔阵营。", encoding="utf-8")

            registry = {
                "characters": [{"id": "c:1", "name": "艾琳", "source": "canon/chapter_02.md"}],
                "factions": [{"id": "f:1", "name": "灰塔阵营", "source": "canon/chapter_02.md"}],
                "locations": [],
                "events": [],
                "timeline_anchors": [],
                "relationships": [
                    {
                        "id": "r:1",
                        "source_entity": "艾琳",
                        "target_entity": "灰塔阵营",
                        "relation_type": "investigates",
                        "source": "canon/chapter_02.md",
                        "evidence": "调查灰塔阵营",
                    }
                ],
                "aliases": [],
            }
            (project / "workbench" / "extracted" / "registry.json").write_text(
                json.dumps(registry, ensure_ascii=False),
                encoding="utf-8",
            )

            text_out = retrieve_text(
                query="灰塔阵营",
                top_k=1,
                config=RetrievalConfig(project_id="p2", projects_root=projects_root),
            )
            self.assertEqual(len(text_out["results"]), 1)
            self.assertIn("chapter_02.md", text_out["results"][0]["source"])

            graph_out = retrieve_graph(
                "艾琳和灰塔阵营有什么关系？",
                config=GraphConfig(project_id="p2", projects_root=projects_root),
            )
            self.assertEqual(graph_out["answer_type"], "relationship_between")


if __name__ == "__main__":
    unittest.main()
