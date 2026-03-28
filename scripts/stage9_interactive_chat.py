"""Single-window interactive chat entry with optional forced draft writes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from story_agent_workbench.chat import append_turn, generate_reply, load_recent_turns
from story_agent_workbench.graph.graph_retriever import GraphConfig
from story_agent_workbench.retrieval.text_retriever import RetrievalConfig
from story_agent_workbench.router.agent_router import route_query
from story_agent_workbench.strategy import load_strategy_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive story-agent chat")
    parser.add_argument("--session-id", default="interactive", help="Persistent session id")
    parser.add_argument("--memory-turns", type=int, default=8, help="Turns to keep")
    parser.add_argument("--mode", choices=["chat", "feedback", "critic", "evidence"], default="chat")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--show-evidence", action="store_true")
    parser.add_argument("--auto-draft", action="store_true", help="Force builder to save draft assets every turn")
    parser.add_argument("--data-root", default="data/samples")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--projects-root", default="projects")
    parser.add_argument("--index-path", default="data/workbench/index/text_index.json")
    parser.add_argument("--rebuild-index", action="store_true")
    parser.add_argument("--registry-path", default="data/extracted/registry.json")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    strategy = load_strategy_config()

    retrieval_config = RetrievalConfig(
        data_root=Path(args.data_root),
        project_id=args.project_id,
        project_root=Path(args.project_root) if args.project_root else None,
        projects_root=Path(args.projects_root),
        index_path=Path(args.index_path),
        rebuild_index=args.rebuild_index,
    )
    graph_config = GraphConfig(
        registry_path=Path(args.registry_path),
        project_id=args.project_id,
        project_root=Path(args.project_root) if args.project_root else None,
        projects_root=Path(args.projects_root),
    )

    print("=== Interactive Story Agent ===")
    print("Type /exit to quit")

    while True:
        try:
            query = input("你> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye")
            break

        if not query:
            continue
        if query == "/exit":
            break

        route = route_query(query, strategy=strategy)
        memory_turns = load_recent_turns(args.session_id, args.memory_turns)
        response = generate_reply(
            query=query,
            mode=args.mode,
            show_evidence=args.show_evidence,
            top_k=args.top_k,
            retrieval_config=retrieval_config,
            graph_config=graph_config,
            strategy=strategy,
            route_decision=route,
            memory_turns=memory_turns,
            auto_draft=args.auto_draft,
        )
        append_turn(
            session_id=args.session_id,
            mode=response["mode"],
            user_query=query,
            assistant_reply=response["reply"],
            keep_turns=args.memory_turns,
        )

        payload = {"route": route, "response": response}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(response["reply"])
            if response.get("builder_saved_assets"):
                print("saved:", len(response["builder_saved_assets"]))


if __name__ == "__main__":
    main()
