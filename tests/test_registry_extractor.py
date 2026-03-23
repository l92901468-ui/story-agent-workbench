import json
import tempfile
import unittest
from pathlib import Path

from story_agent_workbench.graph.extractor import extract_registry_from_canon


class TestRegistryExtractor(unittest.TestCase):
    def test_extract_registry_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "registry.json"
            registry = extract_registry_from_canon(
                data_root=Path("data/samples"),
                output_path=out,
                use_llm=False,
            )
            self.assertTrue(out.exists())
            raw = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("characters", raw)
            self.assertGreaterEqual(len(registry.characters), 1)


if __name__ == "__main__":
    unittest.main()
