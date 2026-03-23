"""Stage-8C unified project workbench session entry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from story_agent_workbench.chat import generate_reply, load_recent_turns
from story_agent_workbench.graph.graph_retriever import GraphConfig
from story_agent_workbench.orchestrator.assets import (
    approve_asset,
    publish_asset,
    reject_asset,
)
from story_agent_workbench.quality import run_project_quality_check
from story_agent_workbench.retrieval.text_retriever import RetrievalConfig
from story_agent_workbench.router.agent_router import route_query
from story_agent_workbench.strategy import load_strategy_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage-8C unified project session")
    parser.add_argument("--project-id", default=None, help="Project id (remembered in session file)")
    parser.add_argument("--projects-root", default="projects", help="Projects root directory")
    parser.add_argument("--session-file", default=".project_session.json", help="Session binding file")
    parser.add_argument("--json", action="store_true", help="Print full JSON")

    sub = parser.add_subparsers(dest="action", required=True)

    chat = sub.add_parser("chat", help="Chat with project context")
    chat.add_argument("query")
    chat.add_argument("--mode", choices=["chat", "feedback", "critic", "evidence"], default="chat")
    chat.add_argument("--top-k", type=int, default=3)
    chat.add_argument("--show-evidence", action="store_true")

    check = sub.add_parser("check", help="Run project quality checks")
    check.add_argument("--top", type=int, default=5, help="Only keep top-N highest confidence issues")

    build = sub.add_parser("build", help="Generate builder assets into draft workbench")
    build.add_argument("query")
    build.add_argument("--mode", choices=["evidence", "critic", "feedback", "chat"], default="evidence")
    build.add_argument("--top-k", type=int, default=3)

    review = sub.add_parser("review", help="List/review/publish assets")
    review.add_argument("--do", choices=["list", "approve", "reject", "publish"], default="list")
    review.add_argument("--status", choices=["all", "draft", "approved", "rejected", "published"], default="all")
    review.add_argument("--asset-path", default=None, help="Required for approve/reject/publish")
    review.add_argument("--note", default="", help="Optional review note")

    return parser


def _resolve_project_binding(project_id: str | None, projects_root: str, session_file: Path) -> tuple[str, Path]:
    if project_id:
        payload = {"project_id": project_id, "projects_root": projects_root}
        session_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return project_id, Path(projects_root)

    if session_file.exists():
        payload = json.loads(session_file.read_text(encoding="utf-8"))
        bound = str(payload.get("project_id", "")).strip()
        root = str(payload.get("projects_root", projects_root))
        if bound:
            return bound, Path(root)

    raise ValueError("project_id is required for first run. Use --project-id to bind session.")


def _list_assets(workbench_root: Path, status_filter: str = "all") -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for path in sorted(workbench_root.rglob("*.json")):
        if "import_manifest.json" in str(path):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        status = str(payload.get("status", "unknown"))
        if status_filter != "all" and status != status_filter:
            continue
        assets.append(
            {
                "asset_id": payload.get("asset_id", ""),
                "asset_type": payload.get("asset_type", payload.get("type", "")),
                "title": payload.get("title", ""),
                "status": status,
                "path": str(path),
            }
        )
    return assets


def _run_chat_action(args: argparse.Namespace, project_id: str, projects_root: Path) -> dict[str, Any]:
    strategy = load_strategy_config()
    route = route_query(args.query, strategy=strategy)
    retrieval_config = RetrievalConfig(project_id=project_id, projects_root=projects_root)
    graph_config = GraphConfig(project_id=project_id, projects_root=projects_root)
    response = generate_reply(
        query=args.query,
        mode=args.mode,
        show_evidence=args.show_evidence,
        top_k=args.top_k,
        retrieval_config=retrieval_config,
        graph_config=graph_config,
        strategy=strategy,
        route_decision=route,
        memory_turns=load_recent_turns(f"project:{project_id}", 3),
    )
    return {
        "action": "chat",
        "project_id": project_id,
        "route": route,
        "response": response,
    }


def _run_check_action(args: argparse.Namespace, project_id: str, projects_root: Path) -> dict[str, Any]:
    report = run_project_quality_check(project_id=project_id, projects_root=projects_root)
    issues = sorted(report["issues"], key=lambda x: float(x.get("confidence", 0.0)), reverse=True)
    report["issues"] = issues[: max(0, args.top)]
    report["issue_count"] = len(report["issues"])
    return {"action": "check", **report}


def _run_build_action(args: argparse.Namespace, project_id: str, projects_root: Path) -> dict[str, Any]:
    strategy = load_strategy_config()
    route = route_query(args.query, strategy=strategy)
    retrieval_config = RetrievalConfig(project_id=project_id, projects_root=projects_root)
    graph_config = GraphConfig(project_id=project_id, projects_root=projects_root)
    response = generate_reply(
        query=args.query,
        mode=args.mode,
        show_evidence=True,
        top_k=args.top_k,
        retrieval_config=retrieval_config,
        graph_config=graph_config,
        strategy=strategy,
        route_decision=route,
        memory_turns=[],
    )
    return {
        "action": "build",
        "project_id": project_id,
        "saved_assets": response.get("builder_saved_assets", []),
        "builder_entries": response.get("builder_entries", []),
    }


def _run_review_action(args: argparse.Namespace, project_id: str, projects_root: Path) -> dict[str, Any]:
    workbench = projects_root / project_id / "workbench"
    if args.do == "list":
        items = _list_assets(workbench, status_filter=args.status)
        return {"action": "review", "project_id": project_id, "count": len(items), "assets": items}

    if not args.asset_path:
        raise ValueError("--asset-path is required for approve/reject/publish")

    if args.do == "approve":
        payload = approve_asset(args.asset_path, note=args.note)
    elif args.do == "reject":
        payload = reject_asset(args.asset_path, note=args.note)
    else:
        payload = publish_asset(args.asset_path, workbench_root=workbench)

    return {"action": "review", "project_id": project_id, "result": payload}


def run_session(argv: list[str] | None = None) -> dict[str, Any]:
    args = build_parser().parse_args(argv)
    project_id, projects_root = _resolve_project_binding(
        args.project_id,
        args.projects_root,
        Path(args.session_file),
    )

    if args.action == "chat":
        return _run_chat_action(args, project_id, projects_root)
    if args.action == "check":
        return _run_check_action(args, project_id, projects_root)
    if args.action == "build":
        return _run_build_action(args, project_id, projects_root)
    if args.action == "review":
        return _run_review_action(args, project_id, projects_root)
    raise ValueError(f"unsupported action: {args.action}")


def main() -> None:
    payload = run_session()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
