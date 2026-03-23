import unittest

from story_agent_workbench.retrieval.text_retriever import RetrievalConfig, retrieve_text


class TestTextRetriever(unittest.TestCase):
    def test_retrieve_top_k_and_fields(self) -> None:
        result = retrieve_text(query="灰塔 线索", top_k=2, config=RetrievalConfig())
        self.assertIn("results", result)
        self.assertLessEqual(len(result["results"]), 2)
        self.assertGreaterEqual(len(result["results"]), 1)
        item = result["results"][0]
        for field in ("source", "chunk_id", "layer", "text", "score"):
            self.assertIn(field, item)


if __name__ == "__main__":
    unittest.main()
