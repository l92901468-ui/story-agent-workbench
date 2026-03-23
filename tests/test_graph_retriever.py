import unittest

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


if __name__ == "__main__":
    unittest.main()
