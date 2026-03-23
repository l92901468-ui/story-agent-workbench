import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestProjectSession(unittest.TestCase):
    def _run(self, args: list[str], cwd: Path) -> dict:
        cmd = ["python", "scripts/stage8c_project_session.py", *args]
        out = subprocess.check_output(cmd, cwd=str(cwd), text=True)
        return json.loads(out)

    def test_check_and_session_binding(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "projects"
            project = root / "p_session"
            (project / "canon").mkdir(parents=True, exist_ok=True)
            (project / "draft").mkdir(parents=True, exist_ok=True)
            (project / "reference").mkdir(parents=True, exist_ok=True)
            (project / "canon" / "chapter_01.md").write_text("characters: 艾琳\n\n剧情文本内容。", encoding="utf-8")
            session_file = Path(tmpdir) / "session.json"

            first = self._run(
                [
                    "--project-id",
                    "p_session",
                    "--projects-root",
                    str(root),
                    "--session-file",
                    str(session_file),
                    "check",
                    "--top",
                    "2",
                ],
                repo_root,
            )
            self.assertEqual(first["action"], "check")
            self.assertEqual(first["project_id"], "p_session")

            second = self._run(
                [
                    "--projects-root",
                    str(root),
                    "--session-file",
                    str(session_file),
                    "check",
                    "--top",
                    "1",
                ],
                repo_root,
            )
            self.assertEqual(second["project_id"], "p_session")

    def test_build_then_review_list(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "projects"
            project = root / "p_build"
            (project / "canon").mkdir(parents=True, exist_ok=True)
            (project / "draft").mkdir(parents=True, exist_ok=True)
            (project / "reference").mkdir(parents=True, exist_ok=True)
            (project / "canon" / "chapter_01.md").write_text("艾琳调查灰塔阵营。", encoding="utf-8")
            session_file = Path(tmpdir) / "session.json"

            build_out = self._run(
                [
                    "--project-id",
                    "p_build",
                    "--projects-root",
                    str(root),
                    "--session-file",
                    str(session_file),
                    "build",
                    "请整理可沉淀条目",
                ],
                repo_root,
            )
            self.assertEqual(build_out["action"], "build")
            self.assertGreaterEqual(len(build_out["saved_assets"]), 1)

            review_out = self._run(
                [
                    "--projects-root",
                    str(root),
                    "--session-file",
                    str(session_file),
                    "review",
                    "--do",
                    "list",
                    "--status",
                    "draft",
                ],
                repo_root,
            )
            self.assertEqual(review_out["action"], "review")
            self.assertGreaterEqual(review_out["count"], 1)


if __name__ == "__main__":
    unittest.main()
