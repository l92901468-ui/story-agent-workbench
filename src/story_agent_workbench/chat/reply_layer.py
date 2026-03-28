"""Stage-5 chat reply layer with routing/reply strategy policies."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from story_agent_workbench.graph.graph_retriever import GraphConfig, retrieve_graph
from story_agent_workbench.orchestrator import orchestrate_hidden_agents
from story_agent_workbench.retrieval.text_retriever import RetrievalConfig, retrieve_text
from story_agent_workbench.strategy import StrategyConfig

MODE_DUTIES = {
    "chat": "轻松聊剧情方向与创作思路。",
    "feedback": "给可执行的修改建议。",
    "critic": "优先挑潜在冲突与不一致。",
    "evidence": "只输出证据片段与来源。",
}


def _format_memory_context(memory_turns: list[dict[str, Any]]) -> str:
    if not memory_turns:
        return ""

    lines = ["最近会话上下文："]
    for turn in memory_turns:
        mode = turn.get("mode", "chat")
        user = str(turn.get("user", "")).strip()
        assistant = str(turn.get("assistant", "")).strip()
        if user:
            lines.append(f"- ({mode}) 用户：{user}")
        if assistant:
            lines.append(f"  助手：{assistant[:120]}")
    return "\n".join(lines)


def _pick_mode(query: str, requested_mode: str, strategy: StrategyConfig) -> tuple[str, str]:
    if requested_mode != "chat" or not strategy.auto_mode_enabled:
        return requested_mode, "requested mode is explicit"

    for candidate, keywords in strategy.mode_keywords.items():
        if any(kw in query for kw in keywords):
            return candidate, f"auto mode switch by keyword match: {candidate}"

    return "chat", "default chat mode"


def _compute_text_confidence(text_retrieval: dict[str, Any] | None) -> float:
    if not text_retrieval:
        return 0.0
    results = text_retrieval.get("results", [])
    if not results:
        return 0.0
    top = float(results[0].get("score", 0.0))
    return min(1.0, top / 3.0)


def _compute_graph_confidence(graph_retrieval: dict[str, Any] | None) -> float:
    if not graph_retrieval:
        return 0.0
    answer_type = graph_retrieval.get("answer_type", "none")
    evidence = graph_retrieval.get("evidence", [])
    if answer_type == "none":
        return 0.0
    if evidence:
        return min(1.0, 0.45 + 0.1 * len(evidence))
    return 0.3


def _use_graph(route_decision: dict[str, Any], mode: str) -> bool:
    return route_decision.get("route") == "graph_retrieval" or mode in {"critic", "evidence"}


def _use_text(route_decision: dict[str, Any], mode: str) -> bool:
    return route_decision.get("route") == "text_retrieval" or mode in {"feedback", "evidence"}


def _try_llm_reply(
    *,
    query: str,
    mode: str,
    text_retrieval: dict[str, Any] | None,
    graph_retrieval: dict[str, Any] | None,
    memory_turns: list[dict[str, Any]],
) -> str | None:
    api_key = os.getenv("API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None

    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None

    context_lines = [f"模式职责：{MODE_DUTIES.get(mode, '')}"]
    memory_block = _format_memory_context(memory_turns)
    if memory_block:
        context_lines.append(memory_block)

    if text_retrieval and text_retrieval.get("results"):
        context_lines.append("文本证据（轻量）：")
        for item in text_retrieval["results"][:2]:
            context_lines.append(f"- {item['source']} | {item['chunk_id']} | score={item['score']}")

    if graph_retrieval and graph_retrieval.get("evidence"):
        context_lines.append("图证据（轻量）：")
        for ev in graph_retrieval["evidence"][:2]:
            context_lines.append(f"- {ev}")

    prompt = "\n".join([f"用户问题：{query}", *context_lines])

    try:
        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        response = client.responses.create(model=model, input=prompt)
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()
    except Exception:
        return None

    return None


def _fallback_reply(
    *,
    mode: str,
    query: str,
    text_retrieval: dict[str, Any] | None,
    graph_retrieval: dict[str, Any] | None,
    confidence_note: str,
    memory_turns: list[dict[str, Any]],
) -> str:
    text_results = text_retrieval.get("results", []) if text_retrieval else []
    graph_evidence = graph_retrieval.get("evidence", []) if graph_retrieval else []

    memory_hint = ""
    if memory_turns:
        last_user = memory_turns[-1].get("user", "")
        if last_user:
            memory_hint = f"（参考你上一轮提到的：{last_user}）"

    uncertain_prefix = ""
    if confidence_note:
        uncertain_prefix = f"[置信提示] {confidence_note}\n"

    if mode == "evidence":
        lines = [uncertain_prefix + "证据模式："]
        if graph_evidence:
            for idx, ev in enumerate(graph_evidence[:5], start=1):
                lines.append(f"[graph-{idx}] {ev}")
        if text_results:
            for idx, item in enumerate(text_results[:3], start=1):
                lines.append(
                    f"[text-{idx}] {item['chunk_id']} | {item['source']} | {item['layer']} | score={item['score']}"
                )
        if len(lines) == 1:
            lines.append("没有命中证据。")
        return "\n".join(lines)

    if mode == "critic":
        if graph_evidence:
            return (
                f"{uncertain_prefix}挑刺模式{memory_hint}：\n"
                "- 我先基于当前图关系给你做一轮全局一致性检查。\n"
                "- 重点看：角色知情时点、阵营链条是否断裂、伏笔是否回收。"
            )
        return (
            f"{uncertain_prefix}挑刺模式：图命中偏弱。先陪你顺一遍剧情逻辑，"
            "再基于已有资料补依据。"
        )

    if mode == "feedback":
        if text_results:
            top = text_results[0]
            return (
                f"{uncertain_prefix}反馈模式{memory_hint}：\n"
                f"- 先围绕 `{top['source']}` 这段做局部改写。\n"
                "- 再检查信息揭示顺序和角色动机连贯性。"
            )
        return f"{uncertain_prefix}反馈模式：先把目标拆成“剧情推进/角色塑造/信息揭示”，再逐段优化。"

    # chat
    if graph_evidence:
        return (
            f"{uncertain_prefix}我先抓到一些全局关系线索{memory_hint}。"
            "要不要我按“角色关系 / 阵营链条 / 事件时间”三条线给你顺一遍？"
        )
    if text_results:
        top = text_results[0]
        return (
            f"{uncertain_prefix}我先找到一段相关文本（{top['source']}）{memory_hint}。"
            "你想先做保守改写，还是冲突加强版？"
        )
    return (
        f"{uncertain_prefix}我们先陪你顺一下思路，再基于现有资料逐步补依据。"
    )


def generate_reply(
    *,
    query: str,
    mode: str,
    show_evidence: bool,
    top_k: int,
    retrieval_config: RetrievalConfig,
    graph_config: GraphConfig | None,
    strategy: StrategyConfig,
    route_decision: dict[str, Any],
    memory_turns: list[dict[str, Any]] | None = None,
    auto_draft: bool = False,
) -> dict[str, Any]:
    if memory_turns is None:
        memory_turns = []

    effective_mode, mode_reason = _pick_mode(query, mode, strategy)

    use_text = _use_text(route_decision, effective_mode)
    use_graph = _use_graph(route_decision, effective_mode)

    text_retrieval: dict[str, Any] | None = None
    graph_retrieval: dict[str, Any] | None = None

    if use_text:
        text_retrieval = retrieve_text(query=query, top_k=top_k, config=retrieval_config)
    if use_graph:
        graph_retrieval = retrieve_graph(query=query, config=graph_config)

    text_conf = _compute_text_confidence(text_retrieval)
    graph_conf = _compute_graph_confidence(graph_retrieval)

    fallback_reason = ""
    if use_graph and graph_conf < strategy.graph_conf_threshold and text_conf >= strategy.text_conf_threshold:
        fallback_reason = "graph weak hit, fallback emphasis to text"
        use_graph = False
        graph_retrieval = None

    if text_conf < strategy.low_confidence_threshold and graph_conf < strategy.low_confidence_threshold:
        fallback_reason = (fallback_reason + "; " if fallback_reason else "") + "both channels weak; answer with uncertainty"

    llm_reply = _try_llm_reply(
        query=query,
        mode=effective_mode,
        text_retrieval=text_retrieval,
        graph_retrieval=graph_retrieval,
        memory_turns=memory_turns,
    )

    reply_text = llm_reply if llm_reply else _fallback_reply(
        mode=effective_mode,
        query=query,
        text_retrieval=text_retrieval,
        graph_retrieval=graph_retrieval,
        confidence_note=fallback_reason,
        memory_turns=memory_turns,
    )

    text_evidence = text_retrieval.get("evidence", []) if text_retrieval else []
    graph_evidence = graph_retrieval.get("evidence", []) if graph_retrieval else []
    orchestration = orchestrate_hidden_agents(
        query=query,
        mode=effective_mode,
        base_reply=reply_text,
        text_evidence=text_evidence,
        graph_evidence=graph_evidence,
        graph_results=graph_retrieval,
        published_root=(
            Path(retrieval_config.project_root) / ".workbench" / "published"
            if retrieval_config.project_root
            else (
                Path(retrieval_config.projects_root) / retrieval_config.project_id / "workbench" / "published"
                if retrieval_config.project_id
                else None
            )
        ),
        draft_root=(
            Path(retrieval_config.project_root) / ".workbench" / "assets" / "draft"
            if retrieval_config.project_root
            else (
                Path(retrieval_config.projects_root) / retrieval_config.project_id / "workbench" / "draft"
                if retrieval_config.project_id
                else None
            )
        ),
        force_builder=auto_draft,
    )
    reply_text = orchestration.final_reply

    payload: dict[str, Any] = {
        "requested_mode": mode,
        "mode": effective_mode,
        "mode_reason": mode_reason,
        "mode_duty": MODE_DUTIES.get(effective_mode, ""),
        "query": query,
        "used_text_retrieval": bool(text_retrieval),
        "used_graph_retrieval": bool(graph_retrieval),
        "route": route_decision.get("route"),
        "route_confidence": route_decision.get("confidence", 0.0),
        "text_confidence": round(text_conf, 3),
        "graph_confidence": round(graph_conf, 3),
        "fallback_reason": fallback_reason,
        "memory_turns_used": len(memory_turns),
        "reply": reply_text,
        "agents_called": orchestration.agents_called,
        "builder_entries": orchestration.builder_entries,
        "builder_saved_assets": orchestration.builder_saved_assets,
        "published_asset_refs": orchestration.published_asset_refs,
    }

    if text_retrieval:
        payload["text_retrieval"] = text_retrieval
    if graph_retrieval:
        payload["graph_retrieval"] = graph_retrieval

    show_full_evidence = effective_mode in strategy.show_full_evidence_modes or show_evidence

    if show_full_evidence:
        payload["evidence"] = {
            "graph": graph_retrieval.get("evidence", []) if graph_retrieval else [],
            "text": text_retrieval.get("evidence", []) if text_retrieval else [],
            "published": [item.get("path", "") for item in orchestration.published_asset_refs[:5]],
        }
    else:
        payload["light_citation"] = {
            "graph": (graph_retrieval.get("evidence", [])[:1] if graph_retrieval else []),
            "text": (text_retrieval.get("evidence", [])[:1] if text_retrieval else []),
        }

    return payload
