import unittest
from unittest.mock import patch

from story_agent_workbench.orchestrator.orchestrator import orchestrate_hidden_agents


class TestOrchestrator(unittest.TestCase):
    def test_story_buddy_default(self) -> None:
        out = orchestrate_hidden_agents(
            query="我想顺一下剧情",
            mode="chat",
            base_reply="基础回复",
            text_evidence=[],
            graph_evidence=[],
            graph_results=None,
        )
        self.assertIn("orchestrator", out.agents_called)
        self.assertIn("story_buddy", out.agents_called)

    def test_critic_trigger(self) -> None:
        out = orchestrate_hidden_agents(
            query="这里会不会有冲突",
            mode="chat",
            base_reply="基础回复",
            text_evidence=[],
            graph_evidence=["A -> B"],
            graph_results={"answer_type": "relationship_between"},
        )
        self.assertIn("critic", out.agents_called)

    def test_systems_designer_trigger(self) -> None:
        out = orchestrate_hidden_agents(
            query="这个任务机制怎么设计互动",
            mode="chat",
            base_reply="基础回复",
            text_evidence=[],
            graph_evidence=[],
            graph_results=None,
        )
        self.assertIn("systems_designer", out.agents_called)

    @patch("story_agent_workbench.orchestrator.roles.persist_builder_assets")
    def test_builder_trigger_by_keyword(self, mock_persist) -> None:
        mock_persist.return_value = [
            {"type": "character_card", "title": "艾琳 角色卡", "path": "data/workbench/draft/characters/demo.json"}
        ]
    def test_builder_trigger_by_keyword(self) -> None:
        out = orchestrate_hidden_agents(
            query="请帮我整理成结构化条目",
            mode="chat",
            base_reply="基础回复",
            text_evidence=[],
            graph_evidence=[],
            graph_results={"answer_type": "character_context", "results": {"character": "艾琳"}},
        )
        self.assertIn("builder", out.agents_called)
        self.assertGreaterEqual(len(out.builder_entries), 1)
        self.assertGreaterEqual(len(out.builder_saved_assets), 1)
        for entry in out.builder_entries:
            self.assertIn("type", entry)
            self.assertIn("title", entry)
            self.assertIn("summary", entry)
            self.assertIn("source_query", entry)

    @patch("story_agent_workbench.orchestrator.roles.persist_builder_assets")
    def test_builder_trigger_in_evidence_mode(self, mock_persist) -> None:
        mock_persist.return_value = [
            {"type": "open_question", "title": "待确认问题", "path": "data/workbench/draft/open_questions/demo.json"}
        ]
        for entry in out.builder_entries:
            self.assertIn("type", entry)
            self.assertIn("title", entry)
            self.assertIn("content", entry)

    def test_builder_trigger_in_evidence_mode(self) -> None:
        out = orchestrate_hidden_agents(
            query="这轮先不整理",
            mode="evidence",
            base_reply="基础回复",
            text_evidence=[],
            graph_evidence=[],
            graph_results=None,
        )
        self.assertIn("builder", out.agents_called)
        self.assertTrue(any(item.get("type") == "open_question" for item in out.builder_entries))

    def test_builder_trigger_by_force_flag(self) -> None:
        out = orchestrate_hidden_agents(
            query="这轮不含整理关键词",
            mode="chat",
            base_reply="基础回复",
            text_evidence=[],
            graph_evidence=[],
            graph_results=None,
            force_builder=True,
        )
        self.assertIn("builder", out.agents_called)

    @patch("story_agent_workbench.orchestrator.orchestrator.find_relevant_published_assets")
    @patch("story_agent_workbench.orchestrator.orchestrator.load_published_assets")
    def test_published_assets_can_influence_reply(self, mock_load, mock_find) -> None:
        mock_load.return_value = [{"asset_id": "r-1", "asset_type": "relationship_card", "status": "published"}]
        mock_find.return_value = [
            {
                "asset_id": "r-1",
                "asset_type": "relationship_card",
                "title": "艾琳与灰塔阵营关系",
                "path": "data/workbench/published/relationships/r-1.json",
                "score": 2,
            }
        ]
        out = orchestrate_hidden_agents(
            query="帮我看下艾琳和灰塔关系是否矛盾",
            mode="chat",
            base_reply="基础回复",
            text_evidence=[],
            graph_evidence=[],
            graph_results=None,
        )
        self.assertGreaterEqual(len(out.published_asset_refs), 1)
        self.assertIn("已发布资产", out.final_reply)


if __name__ == "__main__":
    unittest.main()
