"""Stage-5 router with configurable strategy and confidence output."""

from __future__ import annotations

from typing import Any

from story_agent_workbench.strategy import StrategyConfig


def _keyword_score(query: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw and kw in query)
    return min(1.0, hits / max(1, len(keywords) / 2))


def route_query(query: str, strategy: StrategyConfig) -> dict[str, Any]:
    """Return route decision with reason and confidence."""

    graph_score = _keyword_score(query, strategy.route_graph_keywords)
    text_score = _keyword_score(query, strategy.route_text_keywords)

    if graph_score >= strategy.route_graph_threshold and graph_score >= text_score:
        route = "graph_retrieval"
        confidence = graph_score
        reason = "graph keyword score is dominant"
    elif text_score >= strategy.route_text_threshold:
        route = "text_retrieval"
        confidence = text_score
        reason = "text keyword score is dominant"
    else:
        route = "text_retrieval"
        confidence = 0.2
        reason = "no strong route signal; fallback to text"

    return {
        "route": route,
        "reason": reason,
        "confidence": round(confidence, 3),
        "query": query,
        "scores": {
            "graph": round(graph_score, 3),
            "text": round(text_score, 3),
        },
    }
