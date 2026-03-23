import json
import tempfile
import unittest
from pathlib import Path

from story_agent_workbench.orchestrator.assets import (
    BuilderAsset,
    build_builder_assets,
    persist_builder_assets,
)


class TestBuilderAssets(unittest.TestCase):
    def test_build_assets_support_required_types(self) -> None:
        assets_character = build_builder_assets(
            query="请整理角色并补事件与伏笔，后续做玩法任务",
            graph_results={"answer_type": "character_context", "results": {"character": "艾琳"}},
            text_evidence=["chunk_001 | data/samples/canon/chapter_01.md | canon | ..."],
            graph_evidence=["艾琳 -> 灰塔阵营 (investigates) | data/samples/canon/chapter_01.md"],
        )
        assets_relationship = build_builder_assets(
            query="请整理关系卡",
            graph_results={
                "answer_type": "relationship_between",
                "results": {"entity_a": "艾琳", "entity_b": "灰塔阵营", "relationships": []},
            },
            text_evidence=[],
            graph_evidence=[],
        )

        all_types = {item.type for item in assets_character + assets_relationship}
        self.assertIn("character_card", all_types)
        self.assertIn("relationship_card", all_types)
        self.assertIn("event_card", all_types)
        self.assertIn("open_question", all_types)
        self.assertIn("foreshadowing_item", all_types)
        self.assertIn("gameplay_hook", all_types)

    def test_persist_assets_to_draft_workbench(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "workbench" / "draft"
            assets = [
                BuilderAsset(
                    type="open_question",
                    title="待确认问题",
                    summary="测试沉淀",
                    source_query="这段是否有冲突？",
                    reference_sources=["data/samples/canon/chapter_01.md"],
                    generated_at="2026-03-23T00:00:00+00:00",
                )
            ]

            saved = persist_builder_assets(assets, root=root)
            self.assertEqual(len(saved), 1)
            saved_path = Path(saved[0]["path"])
            self.assertTrue(saved_path.exists())
            self.assertIn("open_questions", str(saved_path))

            payload = json.loads(saved_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["type"], "open_question")
            self.assertEqual(payload["source_query"], "这段是否有冲突？")
            self.assertIn("reference_sources", payload)
            self.assertIn("generated_at", payload)


if __name__ == "__main__":
    unittest.main()
