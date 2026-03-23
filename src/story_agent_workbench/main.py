"""CLI entry for stage-5 routing and reply strategy layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from story_agent_workbench.chat import append_turn, generate_reply, load_recent_turns
from story_agent_workbench.graph.graph_retriever import GraphConfig
from story_agent_workbench.retrieval.text_retriever import RetrievalConfig
from story_agent_workbench.router.agent_router import route_query
from story_agent_workbench.strategy import DEFAULT_STRATEGY_PATH, load_strategy_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Story Agent Workbench (stage-5 strategy layer)")
    parser.add_argument("query", help="Question or query text")
    parser.add_argument("--top-k", type=int, default=3, help="How many retrieval results to keep")
    parser.add_argument(
        "--mode",
        choices=["chat", "feedback", "critic", "evidence"],
        default="chat",
        help="Reply mode (default: chat). Strategy layer may auto-switch from chat when query intent is explicit.",
    )
    parser.add_argument(
        "--show-evidence",
        action="store_true",
        help="Show full evidence in non-evidence modes",
    )
    parser.add_argument("--session-id", default="default", help="Session identifier for local memory")
    parser.add_argument("--memory-turns", type=int, default=3, help="Recent turns to keep")
    parser.add_argument("--data-root", default="data/samples", help="Input docs root")
    parser.add_argument("--project-id", default=None, help="Optional project id under projects/<project_id>/")
    parser.add_argument("--project-root", default=None, help="Optional direct project root path")
    parser.add_argument("--projects-root", default="projects", help="Projects root directory")
    parser.add_argument("--chunk-size", type=int, default=300, help="Chunk size for text retrieval")
    parser.add_argument("--overlap", type=int, default=40, help="Chunk overlap for text retrieval")
    parser.add_argument("--registry-path", default="data/extracted/registry.json", help="Graph registry JSON path")
    parser.add_argument(
        "--strategy-config",
        default=str(DEFAULT_STRATEGY_PATH),
        help="Routing/reply strategy config path",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON output")
    return parser


def format_human_output(payload: dict[str, Any]) -> str:
    lines: list[str] = []

    route = payload["route"]
    response = payload["response"]

    lines.append("=== Story Agent Workbench ===")
    lines.append(f"requested_mode: {response['requested_mode']}")
    lines.append(f"mode: {response['mode']} ({response['mode_reason']})")
    lines.append(f"query: {response['query']}")
    lines.append(
        f"route: {route['route']} | confidence={route['confidence']} | reason={route['reason']} | scores={route['scores']}"
    )
    lines.append(
        f"channel_confidence: text={response['text_confidence']} graph={response['graph_confidence']}"
    )
    lines.append(f"memory_turns_used: {response.get('memory_turns_used', 0)}")
    lines.append(f"agents_called: {response.get('agents_called', [])}")

    lines.append("\n--- reply ---")
    lines.append(response["reply"])

    if response.get("fallback_reason"):
        lines.append(f"\n[Fallback] {response['fallback_reason']}")

    evidence_obj = response.get("evidence")
    if evidence_obj:
        lines.append("\n--- evidence (full) ---")
        for ev in evidence_obj.get("graph", [])[:5]:
            lines.append(f"[graph] {ev}")
        for ev in evidence_obj.get("text", [])[:5]:
            lines.append(f"[text] {ev}")
    elif response.get("light_citation"):
        lines.append("\n--- citation (light) ---")
        for ev in response["light_citation"].get("graph", [])[:1]:
            lines.append(f"[graph] {ev}")
        for ev in response["light_citation"].get("text", [])[:1]:
            lines.append(f"[text] {ev}")

    if response.get("builder_entries"):
        lines.append("\n--- builder entries (optional) ---")
        for item in response["builder_entries"][:3]:
            lines.append(f"[{item.get('type')}] {item.get('title')}")
    if response.get("builder_saved_assets"):
        lines.append("\n--- builder assets saved ---")
        for item in response["builder_saved_assets"][:5]:
            lines.append(f"[{item.get('asset_type') or item.get('type')}] {item.get('path')}")
    if response.get("published_asset_refs"):
        lines.append("\n--- published assets referenced (light) ---")
        for item in response["published_asset_refs"][:2]:
            lines.append(f"[{item.get('asset_type')}] {item.get('title')} | {item.get('path')}")

    return "\n".join(lines)


def run_cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    strategy = load_strategy_config(args.strategy_config)
    route = route_query(args.query, strategy=strategy)

    text_config = RetrievalConfig(
        data_root=Path(args.data_root),
        project_id=args.project_id,
        project_root=Path(args.project_root) if args.project_root else None,
        projects_root=Path(args.projects_root),
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    graph_config = GraphConfig(
        registry_path=Path(args.registry_path),
        project_id=args.project_id,
        project_root=Path(args.project_root) if args.project_root else None,
        projects_root=Path(args.projects_root),
    )

    memory_turns = load_recent_turns(args.session_id, args.memory_turns)
    response = generate_reply(
        query=args.query,
        mode=args.mode,
        show_evidence=args.show_evidence,
        top_k=args.top_k,
        retrieval_config=text_config,
        graph_config=graph_config,
        strategy=strategy,
        route_decision=route,
        memory_turns=memory_turns,
    )

    append_turn(
        session_id=args.session_id,
        mode=response["mode"],
        user_query=args.query,
        assistant_reply=response["reply"],
        keep_turns=args.memory_turns,
    )

    payload = {
        "route": route,
        "response": response,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_human_output(payload))

    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
