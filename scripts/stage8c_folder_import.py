"""Stage-8D one-command project folder import for no-code users."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from story_agent_workbench.ingest import import_project_folder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage-8D project folder direct import")
    parser.add_argument(
        "--project-root",
        required=True,
        help="Project folder path (contains incoming/canon/draft/reference)",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = import_project_folder(args.project_root)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("=== Stage-8D Folder Import ===")
    print(f"project_root: {report['project_root']}")
    print(f"scanned_files: {report['scanned_files']}")
    print(f"auto_classified_files: {report['auto_classified_files']}")
    print(f"incoming_copied_to_layers: {report['incoming_copied_to_layers']}")
    print(f"chunk_count: {report['chunk_count']}")
    print(f"skipped_files: {len(report['skipped_files'])}")
    print("report: .workbench/logs/import_report.json")


if __name__ == "__main__":
    main()
