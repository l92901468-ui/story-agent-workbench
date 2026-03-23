"""Hidden multi-agent orchestrator (stage-7A)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .roles import builder_role, critic_role, story_buddy_role, systems_designer_role

SYSTEMS_HINTS = {"玩法", "互动", "任务", "机制", "关卡", "奖励", "战斗"}
CRITIC_HINTS = {"冲突", "矛盾", "不一致", "漏洞", "动机"}
BUILDER_HINTS = {"整理", "沉淀", "条目", "卡", "清单", "结构化"}


@dataclass
class OrchestrationResult:
    final_reply: str
    agents_called: list[str]
    builder_entries: list[dict[str, Any]]
    builder_saved_assets: list[dict[str, Any]]


def orchestrate_hidden_agents(
    *,
    query: str,
    mode: str,
    base_reply: str,
    text_evidence: list[str],
    graph_evidence: list[str],
    graph_results: dict[str, Any] | None,
) -> OrchestrationResult:
    """Decide which internal roles to call while keeping single front reply."""

    agents_called: list[str] = ["orchestrator", "story_buddy"]
    final_reply = story_buddy_role(base_reply=base_reply)
    builder_entries: list[dict[str, Any]] = []
    builder_saved_assets: list[dict[str, Any]] = []

    needs_critic = mode == "critic" or any(k in query for k in CRITIC_HINTS)
    needs_systems = any(k in query for k in SYSTEMS_HINTS)
    needs_builder = any(k in query for k in BUILDER_HINTS) or mode == "evidence"

    if needs_critic:
        agents_called.append("critic")
        critique = critic_role(graph_evidence=graph_evidence, text_evidence=text_evidence)
        final_reply += "\n\n另外，我先帮你做了一个内部一致性检查：" + critique

    if needs_systems:
        agents_called.append("systems_designer")
        systems_note = systems_designer_role(query=query)
        final_reply += "\n\n如果你关心玩法结构，我补一个系统设计视角：" + systems_note

    if needs_builder:
        agents_called.append("builder")
        builder_entries, builder_saved_assets = builder_role(
            query=query,
            graph_results=graph_results,
            text_evidence=text_evidence,
            graph_evidence=graph_evidence,
        )
        final_reply += "\n\n我还顺手整理了可沉淀条目，并已保存到 workbench draft 资产区。"
        builder_entries = builder_role(query=query, graph_results=graph_results)
        final_reply += "\n\n我还顺手整理了可沉淀条目（可选查看）。"

    return OrchestrationResult(
        final_reply=final_reply,
        agents_called=agents_called,
        builder_entries=builder_entries,
        builder_saved_assets=builder_saved_assets,
    )
