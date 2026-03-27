"""Minimal stage-7C asset review and publish workflow CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from story_agent_workbench.orchestrator.assets import (
    approve_asset,
    list_draft_assets,
    publish_asset,
    reject_asset,
    review_asset,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage-7C asset review/publish workflow")
    parser.add_argument(
        "--workbench-root",
        default="data/workbench",
        help="Workbench root containing draft/ and published/ directories",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list-draft", help="List draft assets")
    list_cmd.add_argument("--workbench-root", default="data/workbench")

    review = sub.add_parser("review", help="Review one asset with explicit status")
    review.add_argument("--asset-path", required=True, help="Path to draft asset JSON")
    review.add_argument("--status", required=True, choices=["approved", "rejected"])
    review.add_argument("--note", default="", help="Optional review note")
    review.add_argument("--workbench-root", default="data/workbench")

    approve = sub.add_parser("approve", help="Approve one asset")
    approve.add_argument("--asset-path", required=True, help="Path to draft asset JSON")
    approve.add_argument("--note", default="", help="Optional review note")
    approve.add_argument("--workbench-root", default="data/workbench")

    reject = sub.add_parser("reject", help="Reject one asset")
    reject.add_argument("--asset-path", required=True, help="Path to draft asset JSON")
    reject.add_argument("--note", default="", help="Optional review note")
    reject.add_argument("--workbench-root", default="data/workbench")

    publish = sub.add_parser("publish", help="Publish one approved asset")
    publish.add_argument("--asset-path", required=True, help="Path to draft asset JSON")
    publish.add_argument("--workbench-root", default="data/workbench")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(getattr(args, "workbench_root", "data/workbench"))

    if args.command == "list-draft":
        data = list_draft_assets(root=root)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.command == "review":
        updated = review_asset(args.asset_path, status=args.status, note=args.note)
        print(json.dumps(updated, ensure_ascii=False, indent=2))
        return 0

    if args.command == "approve":
        updated = approve_asset(args.asset_path, note=args.note)
        print(json.dumps(updated, ensure_ascii=False, indent=2))
        return 0

    if args.command == "reject":
        updated = reject_asset(args.asset_path, note=args.note)
        print(json.dumps(updated, ensure_ascii=False, indent=2))
        return 0

    if args.command == "publish":
        published = publish_asset(args.asset_path, workbench_root=root)
        print(json.dumps(published, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
