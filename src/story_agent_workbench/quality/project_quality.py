"""Stage-8B minimal project-level structural quality checks."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from story_agent_workbench.core import load_published_assets
from story_agent_workbench.graph.graph_retriever import GraphConfig, load_registry
from story_agent_workbench.ingest.project_importer import import_project_documents

ALLY_HINTS = {"盟友", "合作", "信任", "并肩"}
CONFLICT_HINTS = {"冲突", "敌对", "背叛", "对立", "争执"}
TRANSITION_HINTS = {"后来", "之后", "转而", "逐渐", "最终"}
KNOW_HINTS = {"知道", "得知", "发现", "知晓", "真相"}
FIRST_KNOW_HINTS = {"首次得知", "才知道", "刚知道"}
RESOLUTION_HINTS = {"回收", "揭晓", "兑现", "解释", "收束"}
STRONG_EARLY_KNOW_HINTS = {"早就知道", "早已知道", "一直知道"}
QUALITY_DOC_TYPES = {"chapter", "scene"}
MIN_DOC_LEN = 40
MIN_CONFIDENCE_TO_REPORT = 0.58


@dataclass
class QualityIssue:
    issue_type: str
    summary: str
    confidence: float
    reason: str
    related_sources: list[str]
    related_entities: list[str] = field(default_factory=list)
    suggested_followup: str | None = None
    severity: str = "issue"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_project_texts(project_root: Path) -> list[dict[str, Any]]:
    manifest_path = project_root / "workbench" / "import_manifest.json"
    folder_mode_report = project_root / ".workbench" / "logs" / "import_report.json"
    if folder_mode_report.exists():
        manifest = json.loads(folder_mode_report.read_text(encoding="utf-8"))
    elif manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = import_project_documents(project_id=project_root.name, projects_root=project_root.parent)

    docs = manifest.get("documents", [])
    out: list[dict[str, Any]] = []
    for doc in docs:
        source = str(doc.get("source", ""))
        file_path = project_root / source
        text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        out.append({**doc, "text": text})
    return out


def _parse_timeline(value: str | None) -> int | None:
    if not value:
        return None
    m = re.search(r"(\d+)", value)
    if m:
        return int(m.group(1))
    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    for ch, n in cn_map.items():
        if ch in value:
            return n
    return None


def _collect_characters(docs: list[dict[str, Any]], registry_chars: list[str]) -> list[str]:
    names = set(registry_chars)
    for doc in docs:
        for name in doc.get("characters", []) or []:
            if name:
                names.add(name)
    return sorted(names)


def _quality_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for doc in docs:
        doc_type = str(doc.get("doc_type", ""))
        text_len = int(doc.get("text_length", len(str(doc.get("text", ""))) or 0))
        if doc_type not in QUALITY_DOC_TYPES:
            continue
        if text_len < MIN_DOC_LEN:
            continue
        out.append(doc)
    return out


def _snippet(text: str, keyword: str, *, width: int = 18) -> str:
    idx = text.find(keyword)
    if idx < 0:
        return keyword
    start = max(0, idx - width)
    end = min(len(text), idx + len(keyword) + width)
    return text[start:end].replace("\n", " ")


def _extract_terms(text: str) -> list[str]:
    terms = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", text)
    cjk_runs = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for run in cjk_runs:
        for idx in range(0, len(run) - 1):
            terms.append(run[idx : idx + 2])
    unique: list[str] = []
    seen = set()
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        unique.append(term)
    return unique[:8]


def _check_relationship_conflicts(docs: list[dict[str, Any]], characters: list[str]) -> list[QualityIssue]:
    docs = _quality_docs(docs)
    pair_signals: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
    for doc in docs:
        text = str(doc.get("text", ""))
        src = str(doc.get("source", ""))
        for i, a in enumerate(characters):
            for b in characters[i + 1 :]:
                if a in text and b in text:
                    if any(k in text for k in ALLY_HINTS):
                        pair_signals.setdefault((a, b), []).append(("ally", src, text))
                    if any(k in text for k in CONFLICT_HINTS):
                        pair_signals.setdefault((a, b), []).append(("conflict", src, text))

    issues: list[QualityIssue] = []
    for (a, b), records in pair_signals.items():
        labels = {item[0] for item in records}
        if labels >= {"ally", "conflict"}:
            sources = sorted({item[1] for item in records})
            # false-positive guard: single-source polarity change is often intentional revision.
            if len(sources) < 2:
                continue
            has_transition = any(any(t in item[2] for t in TRANSITION_HINTS) for item in records)
            if has_transition:
                # with explicit transition hints, downgrade and skip issue-level report
                continue
            ally_src = next((src for label, src, _ in records if label == "ally"), "")
            conflict_src = next((src for label, src, _ in records if label == "conflict"), "")
            reason = "同一角色对出现合作与冲突信号。"
            reason += f" ally@{ally_src} vs conflict@{conflict_src}，且未检测到明显关系转变提示。"
            issues.append(
                QualityIssue(
                    issue_type="relationship_conflict",
                    summary=f"{a} 与 {b} 的关系描述可能冲突",
                    confidence=0.82,
                    reason=reason,
                    related_sources=sources,
                    related_entities=[a, b],
                    suggested_followup="在冲突来源附近补过渡句（例如触发事件/立场变化原因）。",
                )
            )
    return issues


def _check_timeline_knowledge(docs: list[dict[str, Any]], characters: list[str]) -> list[QualityIssue]:
    docs = _quality_docs(docs)
    records: list[tuple[str, int, str, str]] = []
    for doc in docs:
        t = _parse_timeline(doc.get("timeline_hint"))
        if t is None:
            continue
        text = str(doc.get("text", ""))
        src = str(doc.get("source", ""))
        for name in characters:
            if name in text and any(k in text for k in KNOW_HINTS):
                records.append((name, t, src, text))

    issues: list[QualityIssue] = []
    by_name: dict[str, list[tuple[int, str, str]]] = {}
    for name, t, src, text in records:
        by_name.setdefault(name, []).append((t, src, text))

    for name, items in by_name.items():
        items.sort(key=lambda x: x[0])
        if len(items) < 2:
            continue
        early = items[0]
        later = items[-1]
        if any(k in later[2] for k in FIRST_KNOW_HINTS):
            if not any(k in early[2] for k in STRONG_EARLY_KNOW_HINTS):
                continue
            if later[0] - early[0] < 1:
                continue
            trigger = next((k for k in STRONG_EARLY_KNOW_HINTS if k in early[2]), "早知道")
            issues.append(
                QualityIssue(
                    issue_type="timeline_knowledge_risk",
                    summary=f"{name} 的知情时点可能过早或顺序可疑",
                    confidence=0.78,
                    reason=(
                        f"较晚时间线出现“首次得知”描述，但较早时间线已有强知情词“{trigger}”"
                        f"（timeline {early[0]} -> {later[0]}）。"
                    ),
                    related_sources=[early[1], later[1]],
                    related_entities=[name],
                    suggested_followup="统一“首次得知”叙事，或把早期表述改为“怀疑/线索”级别。",
                )
            )
    return issues


def _check_unresolved_foreshadowing(docs: list[dict[str, Any]], published_assets: list[dict[str, Any]]) -> list[QualityIssue]:
    f_items = [a for a in published_assets if a.get("asset_type") == "foreshadowing_item"]
    event_items = [a for a in published_assets if a.get("asset_type") == "event_card"]
    if not f_items:
        return []
    all_text = "\n".join(str(doc.get("text", "")) for doc in docs)
    issues: list[QualityIssue] = []
    for item in f_items[:5]:
        summary = str(item.get("summary", ""))
        key_terms = _extract_terms(" ".join([str(item.get("title", "")), summary]))
        linked = [term for term in key_terms if term in all_text]
        if not linked:
            # false-positive guard: foreshadow item not linked to current project corpus
            continue
        if any(any(term in str(ev.get("summary", "")) for term in linked) for ev in event_items):
            # published event already tracks related follow-up, do not report unresolved
            continue
        if any(k in all_text for k in RESOLUTION_HINTS):
            continue
        issues.append(
            QualityIssue(
                issue_type="foreshadowing_unresolved",
                summary=f"可能存在未回收伏笔：{item.get('title', '未命名伏笔')}",
                confidence=0.62,
                reason=f"命中伏笔关键词 {linked[:3]}，但未检测到回收/揭晓信号。",
                related_sources=[str(item.get("path", ""))],
                related_entities=[],
                suggested_followup="补充回收场景，或在条目标注“故意延后回收”。",
            )
        )
    return issues


def _check_faction_chain(registry_factions: list[str], registry_rels: list[tuple[str, str]], docs: list[dict[str, Any]]) -> list[QualityIssue]:
    if not registry_factions:
        return []
    issues: list[QualityIssue] = []
    all_text = "\n".join(str(doc.get("text", "")) for doc in docs)
    for faction in registry_factions:
        degree = sum(1 for a, b in registry_rels if faction in {a, b})
        mentions = all_text.count(faction)
        if degree == 0 or mentions <= 1:
            issues.append(
                QualityIssue(
                    issue_type="faction_chain_gap",
                    summary=f"{faction} 的阵营链条描述可能偏弱",
                    confidence=0.66 if degree == 0 else 0.55,
                    reason=f"关系连接数={degree}，文本提及次数={mentions}，可能缺关键连接节点。",
                    related_sources=[doc.get("source", "") for doc in docs if faction in str(doc.get("text", ""))][:3],
                    related_entities=[faction],
                    suggested_followup="补充阵营与关键人物/事件的显式连接句。",
                )
            )
    return issues


def _check_draft_vs_canon_conflict(docs: list[dict[str, Any]]) -> list[QualityIssue]:
    canon_docs = [doc for doc in docs if doc.get("layer") == "canon"]
    draft_docs = [doc for doc in docs if doc.get("layer") == "draft"]
    issues: list[QualityIssue] = []
    antonym_pairs = [("公开", "保密"), ("合作", "对立"), ("进攻", "撤退")]
    for canon in canon_docs:
        c_text = str(canon.get("text", ""))
        if int(canon.get("text_length", len(c_text))) < MIN_DOC_LEN:
            continue
        c_chars = set(canon.get("characters", []) or [])
        for draft in draft_docs:
            d_text = str(draft.get("text", ""))
            if int(draft.get("text_length", len(d_text))) < MIN_DOC_LEN:
                continue
            d_chars = set(draft.get("characters", []) or [])
            if c_chars and d_chars and not (c_chars & d_chars):
                continue
            for a, b in antonym_pairs:
                if a in c_text and b in d_text:
                    issues.append(
                        QualityIssue(
                            issue_type="draft_canon_conflict",
                            summary=f"draft 与 canon 在“{a}/{b}”叙述上可能不一致",
                            confidence=0.74,
                            reason=(
                                f"在 canon({canon.get('source')}) 命中“{a}”，"
                                f"draft({draft.get('source')}) 命中“{b}”，且角色有重叠。"
                            ),
                            related_sources=[str(canon.get("source", "")), str(draft.get("source", ""))],
                            related_entities=sorted(c_chars | d_chars),
                            suggested_followup=f"核对该处是否为有意改写；若是改写建议补注“从{a}到{b}”的转变原因。",
                        )
                    )
                    break
    return issues


def _check_low_confidence_notice(issues: list[QualityIssue], docs: list[dict[str, Any]]) -> list[QualityIssue]:
    if issues:
        return []
    return [
        QualityIssue(
            issue_type="low_confidence_notice",
            summary="当前检查未发现高置信问题",
            confidence=0.3,
            reason=f"可用证据较少（docs={len(docs)}），建议补充更多 timeline/关系显式描述。",
            related_sources=[str(doc.get("source", "")) for doc in docs[:3]],
            related_entities=[],
            suggested_followup="增加角色关系和时间线标记后重跑检查。",
            severity="warning",
        )
    ]


def run_project_quality_check(
    *,
    project_id: str | None = None,
    project_root: Path | str | None = None,
    projects_root: Path | str = Path("projects"),
) -> dict[str, Any]:
    if project_root is not None:
        root = Path(project_root)
        effective_project_id = project_id or root.name
    else:
        if not project_id:
            raise ValueError("project_id is required when project_root is not provided")
        root = Path(projects_root) / project_id
        effective_project_id = project_id
    docs = _load_project_texts(root)
    registry = load_registry(
        GraphConfig(
            project_id=None if project_root is not None else effective_project_id,
            project_root=root if project_root is not None else None,
            projects_root=Path(projects_root),
        )
    )
    published_root = root / ".workbench" / "published" if (root / ".workbench").exists() else root / "workbench" / "published"
    published = load_published_assets(root=published_root)

    characters = _collect_characters(docs, [c.name for c in registry.characters])
    rel_pairs = [(r.source_entity, r.target_entity) for r in registry.relationships]

    issues: list[QualityIssue] = []
    issues.extend(_check_relationship_conflicts(docs, characters))
    issues.extend(_check_timeline_knowledge(docs, characters))
    issues.extend(_check_unresolved_foreshadowing(docs, published))
    issues.extend(_check_faction_chain([f.name for f in registry.factions], rel_pairs, docs))
    issues.extend(_check_draft_vs_canon_conflict(docs))
    issues = [item for item in issues if item.confidence >= MIN_CONFIDENCE_TO_REPORT]
    issues.extend(_check_low_confidence_notice(issues, docs))

    return {
        "project_id": effective_project_id,
        "project_root": str(root),
        "projects_root": str(projects_root),
        "issue_count": len(issues),
        "issues": [item.to_dict() for item in issues],
    }
