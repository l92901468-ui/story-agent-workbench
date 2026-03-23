"""CLI entry for stage-4 minimal graph-aware chat layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from story_agent_workbench.chat import append_turn, generate_reply, load_recent_turns
from story_agent_workbench.graph.graph_retriever import GraphConfig
from story_agent_workbench.retrieval.text_retriever import RetrievalConfig
from story_agent_workbench.router.agent_router import route_query


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Story Agent Workbench (stage-4 minimal graph layer)")
    parser.add_argument("query", help="Question or query text")
    parser.add_argument("--top-k", type=int, default=3, help="How many retrieval results to keep")
    parser.add_argument(
        "--mode",
        choices=["chat", "feedback", "critic", "evidence"],
        default="chat",
        help="Reply mode: chat/feedback/critic/evidence",
    )
    parser.add_argument(
        "--show-evidence",
        action="store_true",
        help="Show evidence lines in non-evidence modes",
    )
    parser.add_argument(
        "--session-id",
        default="default",
        help="Session identifier used for minimal local memory (default: default)",
    )
    parser.add_argument(
        "--memory-turns",
        type=int,
        default=3,
        help="How many recent turns to remember per session (default: 3)",
    )
    parser.add_argument(
        "--data-root",
        default="data/samples",
        help="Input docs root (default: data/samples)",
    )
    parser.add_argument("--chunk-size", type=int, default=300, help="Chunk size used for text retrieval")
    parser.add_argument("--overlap", type=int, default=40, help="Chunk overlap used for text retrieval")
    parser.add_argument(
        "--registry-path",
        default="data/extracted/registry.json",
        help="Path to extracted graph registry JSON",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON output (default prints readable summary)",
    )
    return parser


def format_human_output(payload: dict[str, Any]) -> str:
    lines: list[str] = []

    route = payload["route"]
    response = payload["response"]

    lines.append("=== Story Agent Workbench ===")
    lines.append(f"mode: {response['mode']}")
    lines.append(f"query: {response['query']}")
    lines.append(f"route: {route['route']} ({route['reason']})")
    lines.append(f"used_text_retrieval: {response['used_text_retrieval']}")
    lines.append(f"used_graph_retrieval: {response['used_graph_retrieval']}")
    lines.append(f"memory_turns_used: {response.get('memory_turns_used', 0)}")

    lines.append("\n--- reply ---")
    lines.append(response["reply"])

    evidence_obj = response.get("evidence")
    if evidence_obj:
        lines.append("\n--- evidence (optional) ---")
        for ev in evidence_obj.get("graph", [])[:5]:
            lines.append(f"[graph] {ev}")
        for ev in evidence_obj.get("text", [])[:5]:
            lines.append(f"[text] {ev}")

    if response.get("text_retrieval"):
        stats = response["text_retrieval"]["stats"]
        lines.append(
            f"\ntext stats: total_chunks={stats['total_chunks']} matched_chunks={stats['matched_chunks']}"
        )

    if response.get("graph_retrieval"):
        graph = response["graph_retrieval"]
        lines.append(
            f"graph stats: answer_type={graph.get('answer_type')} matched_entities={graph.get('matched_entities', [])}"
        )

    return "\n".join(lines)


def run_cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    route = route_query(args.query)
    text_config = RetrievalConfig(
        data_root=Path(args.data_root),
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    graph_config = GraphConfig(registry_path=Path(args.registry_path))

    memory_turns = load_recent_turns(args.session_id, args.memory_turns)
    response = generate_reply(
        query=args.query,
        mode=args.mode,
        show_evidence=args.show_evidence,
        top_k=args.top_k,
        retrieval_config=text_config,
        graph_config=graph_config,
        memory_turns=memory_turns,
    )

    append_turn(
        session_id=args.session_id,
        mode=args.mode,
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
