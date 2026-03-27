import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from story_agent_workbench.ingest.chunker import chunk_text
from story_agent_workbench.ingest.loader import discover_text_documents, load_text_documents, read_text_file


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

    def test_read_txt_docx_doc_files(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            txt_path = root / "demo.txt"
            txt_path.write_text("txt内容", encoding="utf-8")

            docx_path = root / "demo.docx"
            with ZipFile(docx_path, "w") as zf:
                zf.writestr(
                    "word/document.xml",
                    "<w:document><w:body><w:p><w:r><w:t>docx内容</w:t></w:r></w:p></w:body></w:document>",
                )

            doc_path = root / "demo.doc"
            doc_path.write_bytes(b"legacy doc content")

            self.assertIn("txt内容", read_text_file(txt_path))
            self.assertIn("docx内容", read_text_file(docx_path))
            self.assertIn("legacy doc content", read_text_file(doc_path))


if __name__ == "__main__":
    unittest.main()
