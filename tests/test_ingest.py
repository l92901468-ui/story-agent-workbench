import unittest
from pathlib import Path

from story_agent_workbench.ingest.chunker import chunk_text
from story_agent_workbench.ingest.loader import discover_text_documents, load_text_documents


class TestIngest(unittest.TestCase):
    def test_discover_and_load_documents(self) -> None:
        docs = load_text_documents(Path("data/samples"))
        self.assertGreaterEqual(len(docs), 2)
        layers = {doc.layer for doc in docs}
        self.assertIn("canon", layers)
        self.assertIn("draft", layers)

        files = discover_text_documents(Path("data/samples"))
        self.assertTrue(any(str(path).endswith("chapter_01.md") for path in files))

    def test_chunker_fields(self) -> None:
        chunks = chunk_text(
            text="abcdefg" * 20,
            source="canon/example.md",
            layer="canon",
            chunk_size=30,
            overlap=5,
        )
        self.assertGreaterEqual(len(chunks), 2)
        first = chunks[0]
        for field in ("chunk_id", "source", "layer", "text"):
            self.assertIn(field, first)


if __name__ == "__main__":
    unittest.main()
