"""Internal hidden roles for stage-7A orchestration (LLM-first)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .assets import build_builder_assets, persist_builder_assets


def _resolve_api_key() -> str:
    """Resolve API key from preferred env vars.

    Priority:
    1) API_KEY
    2) OPENAI_API_KEY
    """

    return os.getenv("API_KEY", "") or os.getenv("OPENAI_API_KEY", "")


def _call_role_llm(*, role_name: str, system_prompt: str, user_prompt: str, max_output_tokens: int = 260) -> str | None:
    """Call OpenAI Responses API for one internal role.

    Returns None on any error so caller can safely fallback to local templates.
    """

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
    """Default companion tone: keep reply natural and collaborative."""

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


def critic_role(*, query: str, graph_evidence: list[str], text_evidence: list[str]) -> str:
    llm = _call_role_llm(
        role_name="critic",
        system_prompt=(
            "你是叙事一致性审校角色。请根据给定证据，输出 2-3 条可执行的风险检查点。"
            "要简短、具体，避免空话。"
        ),
        user_prompt=(
            f"用户问题：{query}\n"
            f"图证据：{graph_evidence[:3]}\n"
            f"文本证据：{text_evidence[:3]}"
        ),
        max_output_tokens=220,
    )
    if llm:
        return llm

    if graph_evidence:
        return "建议优先核对角色关系与阵营链条是否前后一致，再确认信息揭示时点是否过早。"
    if text_evidence:
        return "建议先检查这几段证据对应的设定是否互相冲突，尤其是角色动机变化。"
    return "当前证据偏少，先标记潜在冲突点，后续补更多依据再做结论。"


def systems_designer_role(*, query: str) -> str:
    llm = _call_role_llm(
        role_name="systems_designer",
        system_prompt=(
            "你是叙事玩法设计顾问。请给出一个最小可执行的玩法结构建议，"
            "格式为“目标-反馈-代价”，控制在 2-4 句话。"
        ),
        user_prompt=f"用户问题：{query}",
        max_output_tokens=220,
    )
    if llm:
        return llm

    return (
        "从玩法/互动设计角度，可以把这一段拆成“目标-反馈-代价”三步，"
        "让玩家行为与叙事结果形成闭环。"
    )


def _summarize_builder_entries_with_llm(*, query: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use LLM to enrich builder entries summary field (best-effort)."""

    llm = _call_role_llm(
        role_name="builder",
        system_prompt=(
            "你是叙事资产整理助手。请把输入的 JSON 数组原样返回，但为每项补充/更新 summary 字段，"
            "要求 summary 是一句可执行说明。只返回 JSON。"
        ),
        user_prompt=f"用户问题：{query}\nentries={json.dumps(entries, ensure_ascii=False)}",
        max_output_tokens=450,
    )
    if not llm:
        return entries

    try:
        parsed = json.loads(llm)
    except json.JSONDecodeError:
        return entries

    if not isinstance(parsed, list):
        return entries

    normalized: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        normalized.append(item)

    return normalized if normalized else entries


def builder_role(
    *,
    query: str,
    graph_results: dict[str, Any] | None,
    text_evidence: list[str],
    graph_evidence: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return and persist stage-7B structured draft assets for 沉淀."""

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

    entries = _summarize_builder_entries_with_llm(query=query, entries=entries)
    saved = persist_builder_assets(assets)
    return entries, saved
