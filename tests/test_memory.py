import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from story_agent_workbench.chat import memory


class TestMemory(unittest.TestCase):
    def test_keep_turns_zero_keeps_empty_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir) / "sessions"
            with mock.patch.object(memory, "SESSION_DIR", session_dir):
                memory.append_turn(
                    session_id="demo",
                    mode="chat",
                    user_query="hello",
                    assistant_reply="world",
                    keep_turns=0,
                )
                self.assertEqual(memory.load_recent_turns("demo", 5), [])
                raw = json.loads((session_dir / "demo.json").read_text(encoding="utf-8"))
                self.assertEqual(raw, [])


if __name__ == "__main__":
    unittest.main()
