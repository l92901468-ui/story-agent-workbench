"""Minimal router with stage-4 graph-aware path selection."""

from __future__ import annotations

from typing import Any

GRAPH_HINT_KEYWORDS = {
    "关系",
    "阵营",
    "全局",
    "链条",
    "关联",
    "冲突",
    "谁和谁",
    "哪些人物",
}


def route_query(query: str) -> dict[str, Any]:
    """Return a minimal route decision structure."""

    if any(keyword in query for keyword in GRAPH_HINT_KEYWORDS):
        return {
            "route": "graph_retrieval",
            "reason": "query contains global-relation hints (stage-4 minimal graph path)",
            "query": query,
        }

    return {
        "route": "text_retrieval",
        "reason": "default route for local text lookup",
        "query": query,
    }
