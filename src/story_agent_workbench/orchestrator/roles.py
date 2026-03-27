"""Internal hidden roles for stage-7A orchestration (LLM-first)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .assets import BuilderAsset, build_builder_assets, persist_builder_assets


def _resolve_api_key() -> str:
    return os.getenv("API_KEY", "") or os.getenv("OPENAI_API_KEY", "")


def _call_role_llm(*, role_name: str, system_prompt: str, user_prompt: str, max_output_tokens: int = 260) -> str | None:
    """Call OpenAI Responses API for one internal role; return None on any failure."""

    api_key = _resolve_api_key()
    if not api_key:
        return None

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "max_output_tokens": max_output_tokens,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
        "metadata": {"agent_role": role_name},
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    text = str(data.get("output_text", "")).strip()
    return text or None


def story_buddy_role(*, query: str, base_reply: str) -> str:
    llm = _call_role_llm(
        role_name="story_buddy",
        system_prompt=(
            "你是剧情陪聊协作者。请在不改变原意的前提下，把基础回复润色得更自然、"
            "更像创作搭档。输出 2-4 句话，不要使用 Markdown 标题。"
        ),
        user_prompt=f"用户问题：{query}\n基础回复：{base_reply}",
        max_output_tokens=220,
    )
    return llm if llm else base_reply


def critic_role(
    *,
    query: str,
    graph_evidence: list[str],
    text_evidence: list[str],
    published_asset_refs: list[dict[str, Any]] | None = None,
) -> str:
    llm = _call_role_llm(
        role_name="critic",
        system_prompt="你是叙事一致性审校角色。请根据证据给出 2-3 条可执行的风险检查点。",
        user_prompt=(
            f"用户问题：{query}\n"
            f"图证据：{graph_evidence[:3]}\n"
            f"文本证据：{text_evidence[:3]}\n"
            f"已发布资产参考：{published_asset_refs[:3] if published_asset_refs else []}"
        ),
        max_output_tokens=220,
    )
    if llm:
        return llm

    published_hint = f"（并参考了 {len(published_asset_refs)} 条已发布资产）" if published_asset_refs else ""
    if graph_evidence:
        return f"建议优先核对角色关系与阵营链条是否前后一致，再确认信息揭示时点是否过早。{published_hint}"
    if text_evidence:
        return f"建议先检查这几段证据对应的设定是否互相冲突，尤其是角色动机变化。{published_hint}"
    return f"当前证据偏少，先标记潜在冲突点，后续补更多依据再做结论。{published_hint}"


def systems_designer_role(*, query: str, published_asset_refs: list[dict[str, Any]] | None = None) -> str:
    llm = _call_role_llm(
        role_name="systems_designer",
        system_prompt="你是叙事玩法设计顾问。请给出一个最小可执行的玩法结构建议（目标-反馈-代价）。",
        user_prompt=f"用户问题：{query}",
        max_output_tokens=220,
    )
    if llm:
        return llm

    base = "从玩法/互动设计角度，可以把这一段拆成“目标-反馈-代价”三步，让玩家行为与叙事结果形成闭环。"
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
    """Return and persist stage-7B structured draft assets for 沉淀."""

    assets = _build_assets_with_llm(
        query=query,
        graph_results=graph_results,
        text_evidence=text_evidence,
        graph_evidence=graph_evidence,
        published_asset_refs=published_asset_refs,
    ) or build_builder_assets(
        query=query,
        graph_results=graph_results,
        text_evidence=text_evidence,
        graph_evidence=graph_evidence,
        published_asset_refs=published_asset_refs,
    )
    entries = [
        {
            "type": asset.type,
            "asset_id": asset.asset_id,
            "asset_type": asset.asset_type,
            "title": asset.title,
            "summary": asset.summary,
            "source_query": asset.source_query,
            "reference_sources": asset.reference_sources,
            "generated_at": asset.generated_at,
            "status": asset.status,
            "metadata": asset.metadata,
            # backward compatibility for old callers/tests
            "content": asset.summary,
        }
        for asset in assets
    ]
    saved = persist_builder_assets(assets, root=draft_root or Path("data/workbench/draft"))
    return entries, saved


def _build_assets_with_llm(
    *,
    query: str,
    graph_results: dict[str, Any] | None,
    text_evidence: list[str],
    graph_evidence: list[str],
    published_asset_refs: list[dict[str, Any]] | None,
) -> list[BuilderAsset] | None:
    """Build builder assets using LLM first, fallback handled by caller."""

    llm = _call_role_llm(
        role_name="builder",
        system_prompt=(
            "你是叙事资产构建代理。请把输入上下文转换成资产列表。"
            "只返回 JSON 数组。每个元素至少包含 asset_type/title/summary，"
            "asset_type 只能是：character_card, relationship_card, event_card, open_question, foreshadowing_item, gameplay_hook。"
        ),
        user_prompt=json.dumps(
            {
                "query": query,
                "graph_results": graph_results,
                "text_evidence": text_evidence[:5],
                "graph_evidence": graph_evidence[:5],
                "published_asset_refs": (published_asset_refs or [])[:5],
            },
            ensure_ascii=False,
        ),
        max_output_tokens=700,
    )
    if not llm:
        return None
    try:
        parsed = json.loads(llm)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None

    valid_types = {
        "character_card",
        "relationship_card",
        "event_card",
        "open_question",
        "foreshadowing_item",
        "gameplay_hook",
    }
    now = datetime.now(timezone.utc).isoformat()
    assets: list[BuilderAsset] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        asset_type = str(item.get("asset_type", "")).strip()
        if asset_type not in valid_types:
            continue
        title = str(item.get("title", "")).strip() or f"{asset_type}（LLM）"
        summary = str(item.get("summary", "")).strip() or "LLM 未给出摘要。"
        refs = item.get("reference_sources")
        if not isinstance(refs, list):
            refs = []
        refs = [str(ref).strip() for ref in refs if str(ref).strip()][:8]
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        assets.append(
            BuilderAsset(
                asset_id=f"{asset_type.replace('_', '-')}-{uuid4().hex[:10]}",
                asset_type=asset_type,
                type=asset_type,
                title=title,
                summary=summary,
                source_query=query,
                reference_sources=refs,
                generated_at=now,
                metadata={"llm_generated": True, **metadata},
            )
        )

    return assets or None
