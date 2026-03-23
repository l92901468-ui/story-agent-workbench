"""Internal hidden roles for stage-7A orchestration."""

from __future__ import annotations

from typing import Any

from .assets import build_builder_assets, persist_builder_assets


def story_buddy_role(*, base_reply: str) -> str:
    """Default companion tone: follow user's narrative flow without over-prescribing."""

    return base_reply


def critic_role(*, graph_evidence: list[str], text_evidence: list[str]) -> str:
    if graph_evidence:
        return "建议优先核对角色关系与阵营链条是否前后一致，再确认信息揭示时点是否过早。"
    if text_evidence:
        return "建议先检查这几段证据对应的设定是否互相冲突，尤其是角色动机变化。"
    return "当前证据偏少，先标记潜在冲突点，后续补更多依据再做结论。"


def systems_designer_role(*, query: str) -> str:
    return (
        "从玩法/互动设计角度，可以把这一段拆成“目标-反馈-代价”三步，"
        "让玩家行为与叙事结果形成闭环。"
    )


def builder_role(
    *,
    query: str,
    graph_results: dict[str, Any] | None,
    text_evidence: list[str],
    graph_evidence: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return and persist stage-7B structured draft assets for沉淀."""

    assets = build_builder_assets(
        query=query,
        graph_results=graph_results,
        text_evidence=text_evidence,
        graph_evidence=graph_evidence,
    )
    entries = [
        {
            "type": asset.type,
            "title": asset.title,
            "summary": asset.summary,
            "source_query": asset.source_query,
            "reference_sources": asset.reference_sources,
            "generated_at": asset.generated_at,
            "generation_tag": asset.generation_tag,
            "metadata": asset.metadata,
        }
        for asset in assets
    ]
    saved = persist_builder_assets(assets)
    return entries, saved
