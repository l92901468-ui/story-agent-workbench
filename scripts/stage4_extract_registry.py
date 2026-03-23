"""Run stage-4 minimal canon extraction to JSON registry."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from story_agent_workbench.graph.extractor import extract_registry_from_canon


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage-4 minimal registry extraction")
    parser.add_argument("--data-root", type=Path, default=Path("data/samples"))
    parser.add_argument("--output", type=Path, default=Path("data/extracted/registry.json"))
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM-assisted extraction and use fallback rules only",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    registry = extract_registry_from_canon(
        data_root=args.data_root,
        output_path=args.output,
        use_llm=not args.no_llm,
    )

    print("=== Stage-4 Registry Extraction ===")
    print(f"output: {args.output}")
    print(f"characters={len(registry.characters)}")
    print(f"factions={len(registry.factions)}")
    print(f"locations={len(registry.locations)}")
    print(f"events={len(registry.events)}")
    print(f"timeline_anchors={len(registry.timeline_anchors)}")
    print(f"relationships={len(registry.relationships)}")
    print(f"aliases={len(registry.aliases)}")


if __name__ == "__main__":
    main()
