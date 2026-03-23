"""Internal hidden roles for stage-7A orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .assets import build_builder_assets, persist_builder_assets


def story_buddy_role(*, base_reply: str) -> str:
    """Default companion tone: follow user's narrative flow without over-prescribing."""

    return base_reply


def critic_role(
    *,
    graph_evidence: list[str],
    text_evidence: list[str],
    published_asset_refs: list[dict[str, Any]] | None = None,
) -> str:
    published_hint = ""
    if published_asset_refs:
        published_hint = f"（并参考了 {len(published_asset_refs)} 条已发布资产）"
    if graph_evidence:
        return f"建议优先核对角色关系与阵营链条是否前后一致，再确认信息揭示时点是否过早。{published_hint}"
    if text_evidence:
        return f"建议先检查这几段证据对应的设定是否互相冲突，尤其是角色动机变化。{published_hint}"
    return f"当前证据偏少，先标记潜在冲突点，后续补更多依据再做结论。{published_hint}"


def systems_designer_role(*, query: str, published_asset_refs: list[dict[str, Any]] | None = None) -> str:
    base = (
        "从玩法/互动设计角度，可以把这一段拆成“目标-反馈-代价”三步，"
        "让玩家行为与叙事结果形成闭环。"
    )
    if published_asset_refs:
        base += f"（已对齐 {len(published_asset_refs)} 条已发布资产）"
    return base


def builder_role(
    *,
    query: str,
    graph_results: dict[str, Any] | None,
    text_evidence: list[str],
    graph_evidence: list[str],
    published_asset_refs: list[dict[str, Any]] | None = None,
    draft_root: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return and persist stage-7B structured draft assets for沉淀."""

    assets = build_builder_assets(
        query=query,
        graph_results=graph_results,
        text_evidence=text_evidence,
        graph_evidence=graph_evidence,
        published_asset_refs=published_asset_refs,
    )
    entries = [
        {
            "type": asset.asset_type,
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type,
            "title": asset.title,
            "summary": asset.summary,
            "source_query": asset.source_query,
            "reference_sources": asset.reference_sources,
            "generated_at": asset.generated_at,
            "generation_tag": asset.generation_tag,
            "status": asset.status,
            "reviewed_at": asset.reviewed_at,
            "review_note": asset.review_note,
            "metadata": asset.metadata,
        }
        for asset in assets
    ]
    saved = persist_builder_assets(assets, root=draft_root or Path("data/workbench/draft"))
    return entries, saved
