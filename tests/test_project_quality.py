import json
import tempfile
import unittest
from pathlib import Path

from story_agent_workbench.quality.project_quality import run_project_quality_check


class TestProjectQuality(unittest.TestCase):
    def test_quality_check_covers_structural_issue_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "projects"
            project = root / "p_quality"
            (project / "canon").mkdir(parents=True, exist_ok=True)
            (project / "draft").mkdir(parents=True, exist_ok=True)
            (project / "reference").mkdir(parents=True, exist_ok=True)
            (project / "workbench" / "extracted").mkdir(parents=True, exist_ok=True)
            (project / "workbench" / "published" / "foreshadowing").mkdir(parents=True, exist_ok=True)

            (project / "canon" / "chapter_01.md").write_text(
                "characters: 艾琳, 罗安\n"
                "timeline: 第3夜\n"
                "艾琳与罗安合作并公开情报，才知道灰塔计划。",
                encoding="utf-8",
            )
            (project / "draft" / "scene_01.md").write_text(
                "characters: 艾琳, 罗安\n"
                "timeline: 第2夜\n"
                "艾琳与罗安冲突并坚持保密，艾琳早就知道灰塔计划。",
                encoding="utf-8",
            )
            (project / "reference" / "note.md").write_text("timeline: 第4夜\n灰塔阵营传闻，疑似存在内鬼线索。", encoding="utf-8")

            registry = {
                "characters": [
                    {"id": "c:1", "name": "艾琳", "source": "canon/chapter_01.md"},
                    {"id": "c:2", "name": "罗安", "source": "canon/chapter_01.md"},
                ],
                "factions": [{"id": "f:1", "name": "灰塔阵营", "source": "reference/note.md"}],
                "locations": [],
                "events": [],
                "timeline_anchors": [],
                "relationships": [],
                "aliases": [],
            }
            (project / "workbench" / "extracted" / "registry.json").write_text(
                json.dumps(registry, ensure_ascii=False),
                encoding="utf-8",
            )

            foreshadow = {
                "asset_id": "f-1",
                "asset_type": "foreshadowing_item",
                "title": "灰塔内鬼线索",
                "summary": "埋下了内鬼伏笔",
                "status": "published",
            }
            (project / "workbench" / "published" / "foreshadowing" / "f1.json").write_text(
                json.dumps(foreshadow, ensure_ascii=False),
                encoding="utf-8",
            )

            report = run_project_quality_check(project_id="p_quality", projects_root=root)
            issue_types = {item["issue_type"] for item in report["issues"]}
            self.assertIn("relationship_conflict", issue_types)
            self.assertIn("timeline_knowledge_risk", issue_types)
            self.assertIn("foreshadowing_unresolved", issue_types)
            self.assertIn("faction_chain_gap", issue_types)
            self.assertIn("draft_canon_conflict", issue_types)
            rel_issue = next(item for item in report["issues"] if item["issue_type"] == "relationship_conflict")
            self.assertIn("ally@", rel_issue["reason"])
            self.assertGreaterEqual(len(rel_issue["related_entities"]), 2)
            self.assertTrue(rel_issue["suggested_followup"])

    def test_low_confidence_notice_when_evidence_is_sparse(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "projects"
            project = root / "p_sparse"
            (project / "canon").mkdir(parents=True, exist_ok=True)
            (project / "canon" / "a.md").write_text("短文本", encoding="utf-8")

            report = run_project_quality_check(project_id="p_sparse", projects_root=root)
            issue_types = {item["issue_type"] for item in report["issues"]}
            self.assertIn("low_confidence_notice", issue_types)

    def test_false_positive_reduction_for_transition_and_foreshadow_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "projects"
            project = root / "p_noise"
            (project / "canon").mkdir(parents=True, exist_ok=True)
            (project / "draft").mkdir(parents=True, exist_ok=True)
            (project / "workbench" / "published" / "foreshadowing").mkdir(parents=True, exist_ok=True)

            # transition keywords should suppress relationship conflict issue
            (project / "canon" / "chapter_01.md").write_text(
                "characters: 艾琳, 罗安\n"
                "timeline: 第3夜\n"
                "艾琳与罗安合作执行计划，之后因为物资分配发生冲突。",
                encoding="utf-8",
            )
            (project / "draft" / "scene_01.md").write_text(
                "characters: 艾琳, 罗安\n"
                "timeline: 第4夜\n"
                "艾琳与罗安后来转而和解。",
                encoding="utf-8",
            )

            # unrelated foreshadow should not trigger
            foreshadow = {
                "asset_id": "f-noise",
                "asset_type": "foreshadowing_item",
                "title": "远古王冠谜团",
                "summary": "王冠谜团仍未解释",
                "status": "published",
            }
            (project / "workbench" / "published" / "foreshadowing" / "noise.json").write_text(
                json.dumps(foreshadow, ensure_ascii=False),
                encoding="utf-8",
            )

            report = run_project_quality_check(project_id="p_noise", projects_root=root)
            issue_types = {item["issue_type"] for item in report["issues"]}
            self.assertNotIn("relationship_conflict", issue_types)
            self.assertNotIn("foreshadowing_unresolved", issue_types)

    def test_timeline_filter_requires_strong_early_knowledge_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "projects"
            project = root / "p_timeline"
            (project / "canon").mkdir(parents=True, exist_ok=True)
            (project / "draft").mkdir(parents=True, exist_ok=True)

            # weak early wording should not trigger
            (project / "draft" / "scene_01.md").write_text(
                "characters: 艾琳\n"
                "timeline: 第2夜\n"
                "艾琳知道有些异常，但没有确定情报。",
                encoding="utf-8",
            )
            (project / "canon" / "chapter_01.md").write_text(
                "characters: 艾琳\n"
                "timeline: 第3夜\n"
                "艾琳才知道灰塔计划细节。",
                encoding="utf-8",
            )

            report = run_project_quality_check(project_id="p_timeline", projects_root=root)
            issue_types = {item["issue_type"] for item in report["issues"]}
            self.assertNotIn("timeline_knowledge_risk", issue_types)


if __name__ == "__main__":
    unittest.main()
