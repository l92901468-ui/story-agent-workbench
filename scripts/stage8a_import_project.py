"""Stage-8A minimal project import script."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from story_agent_workbench.ingest import import_project_documents


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage-8A project import pipeline")
    parser.add_argument("--project-id", required=True, help="Project id under projects/<project_id>/")
    parser.add_argument("--projects-root", default="projects", help="Projects root directory")
    parser.add_argument("--json", action="store_true", help="Print full JSON manifest")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = import_project_documents(project_id=args.project_id, projects_root=Path(args.projects_root))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("=== Stage-8A Project Import ===")
    print(f"project_id: {report['project_id']}")
    print(f"project_root: {report['project_root']}")
    print(f"docs: {report['stats']['total_docs']} | by_layer={report['stats']['by_layer']}")
    for check_name, items in report["checks"].items():
        if items:
            print(f"- {check_name}: {len(items)}")
    print("manifest: projects/<project_id>/workbench/import_manifest.json")


if __name__ == "__main__":
    main()
