import json
import tempfile
import unittest
from pathlib import Path

from story_agent_workbench.core import (
    build_runtime_asset_context,
    find_relevant_published_assets,
    load_published_assets,
)


class TestPublishedContext(unittest.TestCase):
    def test_loader_reads_only_published_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workbench = Path(tmpdir) / "workbench"
            published_file = workbench / "published" / "characters" / "a.json"
            published_file.parent.mkdir(parents=True, exist_ok=True)
            published_file.write_text(
                json.dumps(
                    {
                        "asset_id": "c-1",
                        "asset_type": "character_card",
                        "title": "艾琳 角色卡",
                        "summary": "测试",
                        "status": "published",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            draft_file = workbench / "draft" / "characters" / "b.json"
            draft_file.parent.mkdir(parents=True, exist_ok=True)
            draft_file.write_text(
                json.dumps(
                    {
                        "asset_id": "c-2",
                        "asset_type": "character_card",
                        "title": "草稿角色卡",
                        "status": "draft",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            assets = load_published_assets(root=workbench / "published")
            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0]["asset_id"], "c-1")

    def test_runtime_context_can_match_query(self) -> None:
        assets = [
            {
                "asset_id": "r-1",
                "asset_type": "relationship_card",
                "title": "艾琳与灰塔阵营关系",
                "summary": "关系条目",
                "source_query": "整理关系",
                "status": "published",
                "path": "data/workbench/published/relationships/x.json",
            }
        ]
        context = build_runtime_asset_context(assets)
        refs = find_relevant_published_assets("艾琳和灰塔关系", context)
        self.assertGreaterEqual(len(refs), 1)
        self.assertEqual(refs[0]["asset_type"], "relationship_card")


if __name__ == "__main__":
    unittest.main()
