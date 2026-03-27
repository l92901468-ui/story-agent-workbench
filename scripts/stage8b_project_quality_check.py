"""Stage-8B project quality check runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from story_agent_workbench.quality import run_project_quality_check


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage-8B project quality calibration check")
    parser.add_argument("--project-id", required=True, help="Project id under projects/<project_id>/")
    parser.add_argument("--projects-root", default="projects", help="Projects root directory")
    parser.add_argument("--json", action="store_true", help="Print full JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = run_project_quality_check(project_id=args.project_id, projects_root=Path(args.projects_root))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("=== Stage-8B Project Quality Check ===")
    print(f"project_id: {report['project_id']}")
    print(f"issues: {report['issue_count']}")
    for idx, issue in enumerate(report["issues"][:8], start=1):
        print(
            f"[{idx}] {issue['issue_type']} | conf={issue['confidence']} | "
            f"{issue['summary']} | reason={issue['reason']}"
        )


if __name__ == "__main__":
    main()
