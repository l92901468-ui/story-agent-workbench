import unittest
from unittest.mock import patch

from story_agent_workbench.graph.graph_retriever import GraphConfig, retrieve_graph


class TestGraphRetriever(unittest.TestCase):
    def test_relationship_between_entities(self) -> None:
        result = retrieve_graph(
            "艾琳和灰塔阵营有什么关系？",
            config=GraphConfig(),
        )
        self.assertEqual(result["answer_type"], "relationship_between")
        self.assertIn("evidence", result)
        self.assertGreaterEqual(len(result["evidence"]), 1)

    def test_faction_context(self) -> None:
        result = retrieve_graph("灰塔阵营相关的关键人物", config=GraphConfig())
        self.assertEqual(result["answer_type"], "faction_context")

    def test_faction_query_prefers_faction_entity_when_multiple_entities_hit(self) -> None:
        result = retrieve_graph("艾琳和灰塔阵营相关的关键人物有哪些？", config=GraphConfig())
        self.assertEqual(result["answer_type"], "faction_context")
        self.assertEqual(result["results"]["faction"], "灰塔阵营")

    @patch("story_agent_workbench.graph.graph_retriever.find_relevant_published_assets")
    @patch("story_agent_workbench.graph.graph_retriever.load_published_assets")
    def test_published_assets_can_fill_graph_context(self, mock_load, mock_find) -> None:
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
        result = retrieve_graph("艾琳和灰塔关系", config=GraphConfig())
        self.assertEqual(result["answer_type"], "relationship_between")
        self.assertTrue(any("[published]" in item for item in result["evidence"]))


if __name__ == "__main__":
    unittest.main()
