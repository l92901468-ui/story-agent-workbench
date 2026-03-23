"""Stage-4 chat reply layer.

Provides lightweight multi-mode replies with optional text/graph retrieval and short-term memory.
"""

from __future__ import annotations

import os
from typing import Any

from story_agent_workbench.graph.graph_retriever import GraphConfig, retrieve_graph
from story_agent_workbench.retrieval.text_retriever import RetrievalConfig, retrieve_text

RETRIEVAL_HINT_KEYWORDS = {
    "证据",
    "出处",
    "原文",
    "引用",
    "哪段",
    "根据",
    "冲突",
    "角色",
    "阵营",
    "时间线",
    "伏笔",
    "设定",
}

GRAPH_HINT_KEYWORDS = {
    "关系",
    "阵营",
    "全局",
    "链条",
    "关联",
    "谁和谁",
    "哪些人物",
}

MODE_DUTIES = {
    "chat": "轻松聊剧情方向与创作思路。",
    "feedback": "给可执行的修改建议。",
    "critic": "优先挑潜在冲突与不一致。",
    "evidence": "只输出证据片段与来源。",
}


def _should_use_text_retrieval(query: str, mode: str) -> bool:
    if mode in {"feedback"}:
        return True

    lowered = query.lower()
    return any(keyword in lowered for keyword in RETRIEVAL_HINT_KEYWORDS)


def _should_use_graph_retrieval(query: str, mode: str) -> bool:
    if mode in {"critic", "evidence"}:
        return True

    return any(keyword in query for keyword in GRAPH_HINT_KEYWORDS)


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


def _try_llm_reply(
    *,
    query: str,
    mode: str,
    text_retrieval: dict[str, Any] | None,
    graph_retrieval: dict[str, Any] | None,
    memory_turns: list[dict[str, Any]],
) -> str | None:
    """Optional LLM call path.

    Best-effort only:
    - requires openai package
    - requires OPENAI_API_KEY
    """

    if not os.getenv("OPENAI_API_KEY"):
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
        context_lines.append("文本检索证据（节选）：")
        for item in text_retrieval["results"][:2]:
            context_lines.append(
                f"- {item['source']} | {item['chunk_id']} | {item['layer']} | score={item['score']}"
            )

    if graph_retrieval and graph_retrieval.get("evidence"):
        context_lines.append("图检索证据（节选）：")
        for ev in graph_retrieval["evidence"][:3]:
            context_lines.append(f"- {ev}")

    prompt = "\n".join([f"用户问题：{query}", *context_lines])

    try:
        client = OpenAI()
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
    query: str,
    mode: str,
    text_retrieval: dict[str, Any] | None,
    graph_retrieval: dict[str, Any] | None,
    memory_turns: list[dict[str, Any]],
) -> str:
    text_results = text_retrieval.get("results", []) if text_retrieval else []

    memory_hint = ""
    if memory_turns:
        last_user = memory_turns[-1].get("user", "")
        if last_user:
            memory_hint = f"（参考你上一轮提到的：{last_user}）"

    if mode == "evidence":
        lines = ["证据模式："]

        if graph_retrieval:
            lines.append(f"- 图检索类型：{graph_retrieval.get('answer_type', 'none')}")
            for idx, ev in enumerate(graph_retrieval.get("evidence", [])[:5], start=1):
                lines.append(f"  [graph-{idx}] {ev}")

        if text_results:
            for idx, item in enumerate(text_results[:3], start=1):
                lines.append(
                    f"  [text-{idx}] {item['chunk_id']} | {item['source']} | {item['layer']} | score={item['score']}"
                )

        if len(lines) == 1:
            lines.append("- 没有命中证据。")

        return "\n".join(lines)

    if mode == "critic":
        if graph_retrieval and graph_retrieval.get("results"):
            return (
                f"挑刺模式{memory_hint}：\n"
                f"- 图检索类型：{graph_retrieval.get('answer_type')}\n"
                "- 建议先核对这些关系是否与当前 canon 一致，再看 draft 是否提前泄露信息。"
            )
        return "挑刺模式：当前图关系命中较少，建议补充更多 canon 关系抽取后再检查全局冲突。"

    if mode == "feedback":
        if text_results:
            top = text_results[0]
            return (
                f"反馈模式{memory_hint}：\n"
                f"- 先围绕 `{top['source']}` 这段做局部改写，优先澄清角色动机。\n"
                "- 再检查信息揭示顺序，避免角色过早知道关键线索。"
            )
        return "反馈模式：先把目标拆成“剧情推进/角色塑造/信息揭示”，再逐段优化。"

    # mode == chat
    if graph_retrieval and graph_retrieval.get("results"):
        return (
            f"我查到一些全局关系信息{memory_hint}。"
            "如果你愿意，我可以继续按“角色关系 / 阵营链条 / 事件时间”三条线展开。"
        )

    if text_results:
        top = text_results[0]
        return (
            f"我看到一段相关文本{memory_hint}，最相关来源是 `{top['source']}`。"
            "你想先做保守改写，还是冲突加强版？"
        )

    return "我们先轻松聊剧情吧。你更想先改人物关系、冲突节奏，还是设定一致性？"


def generate_reply(
    *,
    query: str,
    mode: str,
    show_evidence: bool,
    top_k: int,
    retrieval_config: RetrievalConfig,
    graph_config: GraphConfig | None = None,
    memory_turns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Generate chat reply with optional text/graph retrieval support."""

    if memory_turns is None:
        memory_turns = []

    use_text = _should_use_text_retrieval(query, mode)
    use_graph = _should_use_graph_retrieval(query, mode)

    text_retrieval: dict[str, Any] | None = None
    graph_retrieval: dict[str, Any] | None = None

    if use_text:
        text_retrieval = retrieve_text(query=query, top_k=top_k, config=retrieval_config)

    if use_graph:
        graph_retrieval = retrieve_graph(query=query, config=graph_config)

    llm_reply = _try_llm_reply(
        query=query,
        mode=mode,
        text_retrieval=text_retrieval,
        graph_retrieval=graph_retrieval,
        memory_turns=memory_turns,
    )
    reply_text = llm_reply if llm_reply else _fallback_reply(
        query=query,
        mode=mode,
        text_retrieval=text_retrieval,
        graph_retrieval=graph_retrieval,
        memory_turns=memory_turns,
    )

    payload: dict[str, Any] = {
        "mode": mode,
        "mode_duty": MODE_DUTIES.get(mode, ""),
        "query": query,
        "used_text_retrieval": use_text,
        "used_graph_retrieval": use_graph,
        "memory_turns_used": len(memory_turns),
        "reply": reply_text,
    }

    if text_retrieval:
        payload["text_retrieval"] = text_retrieval

    if graph_retrieval:
        payload["graph_retrieval"] = graph_retrieval

    if mode == "evidence":
        payload["evidence"] = {
            "graph": graph_retrieval.get("evidence", []) if graph_retrieval else [],
            "text": text_retrieval.get("evidence", []) if text_retrieval else [],
        }
    elif show_evidence:
        payload["evidence"] = {
            "graph": graph_retrieval.get("evidence", []) if graph_retrieval else [],
            "text": text_retrieval.get("evidence", []) if text_retrieval else [],
        }

    return payload
