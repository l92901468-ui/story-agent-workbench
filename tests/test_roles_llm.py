import json
import unittest
from unittest.mock import patch

from story_agent_workbench.orchestrator.roles import builder_role


class TestRolesLLM(unittest.TestCase):
    @patch("story_agent_workbench.orchestrator.roles.persist_builder_assets")
    @patch("story_agent_workbench.orchestrator.roles._call_role_llm")
    def test_builder_role_prefers_llm_assets(self, mock_call_llm, mock_persist) -> None:
        mock_call_llm.return_value = json.dumps(
            [
                {
                    "asset_type": "open_question",
                    "title": "LLM 待确认问题",
                    "summary": "请补充证据链。",
                    "reference_sources": ["canon/ch1.md"],
                    "metadata": {"priority": "high"},
                }
            ],
            ensure_ascii=False,
        )
        mock_persist.return_value = [{"asset_type": "open_question", "path": "x.json"}]

        entries, saved = builder_role(
            query="请整理",
            graph_results=None,
            text_evidence=[],
            graph_evidence=[],
            published_asset_refs=[],
        )

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "LLM 待确认问题")
        self.assertTrue(entries[0]["metadata"].get("llm_generated"))
        self.assertEqual(saved[0]["asset_type"], "open_question")


if __name__ == "__main__":
    unittest.main()
