"""Stage-7B builder asset schema and local draft persistence."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ASSET_DIR_MAP = {
    "character_card": "characters",
    "relationship_card": "relationships",
    "event_card": "events",
    "open_question": "open_questions",
    "foreshadowing_item": "foreshadowing",
    "gameplay_hook": "gameplay_hooks",
}

SYSTEMS_HINTS = {"玩法", "互动", "任务", "机制", "关卡", "奖励", "战斗"}
FORESHADOWING_HINTS = {"伏笔", "回收", "埋线", "暗示"}
EVENT_HINTS = {"事件", "会合", "延迟", "招募", "冲突", "行动"}
SAFE_FILE_RE = re.compile(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+")


@dataclass
class BuilderAsset:
    """Minimal schema for one draft workbench asset."""

    asset_id: str
    asset_type: str
    title: str
    summary: str
    source_query: str
    reference_sources: list[str]
    generated_at: str
    generation_tag: str = "builder_v1"
    status: str = "draft"
    reviewed_at: str | None = None
    review_note: str | None = None
    published_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Keep compatibility with stage-7B output readers.
        data["type"] = self.asset_type
        return data


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_asset_id(asset_type: str) -> str:
    prefix = asset_type.replace("_", "-")
    return f"{prefix}-{uuid4().hex[:10]}"


def _make_asset(
    *,
    asset_type: str,
    title: str,
    summary: str,
    query: str,
    refs: list[str],
    now: str,
    metadata: dict[str, Any] | None = None,
) -> BuilderAsset:
    merged_metadata = {"target_integration": "canon_registry_candidate"}
    if metadata:
        merged_metadata.update(metadata)
    return BuilderAsset(
        asset_id=_new_asset_id(asset_type),
        asset_type=asset_type,
        title=title,
        summary=summary,
        source_query=query,
        reference_sources=refs,
        generated_at=now,
        status="draft",
        metadata=merged_metadata,
    )


def _extract_reference_sources(
    *,
    graph_results: dict[str, Any] | None,
    text_evidence: list[str],
    graph_evidence: list[str],
) -> list[str]:
    refs: list[str] = []

    for item in text_evidence:
        parts = [part.strip() for part in item.split("|")]
        if len(parts) >= 2:
            refs.append(parts[1])

    for item in graph_evidence:
        if "|" in item:
            refs.append(item.split("|")[-1].strip())

    if graph_results:
        result_obj = graph_results.get("results", {})
        if isinstance(result_obj, dict):
            evidence = result_obj.get("evidence", [])
            if isinstance(evidence, list):
                for ev in evidence:
                    if isinstance(ev, dict):
                        source = str(ev.get("source", "")).strip()
                        if source:
                            refs.append(source)

    unique = []
    seen = set()
    for ref in refs:
        if not ref or ref in seen:
            continue
        seen.add(ref)
        unique.append(ref)
    return unique[:8]


def build_builder_assets(
    *,
    query: str,
    graph_results: dict[str, Any] | None,
    text_evidence: list[str],
    graph_evidence: list[str],
    published_asset_refs: list[dict[str, Any]] | None = None,
) -> list[BuilderAsset]:
    """Build minimal stage-7B draft assets from current turn context."""

    refs = _extract_reference_sources(
        graph_results=graph_results,
        text_evidence=text_evidence,
        graph_evidence=graph_evidence,
    )
    if published_asset_refs:
        refs = [*refs, *[str(item.get("path", "")) for item in published_asset_refs if item.get("path")]]
        dedup: list[str] = []
        seen = set()
        for ref in refs:
            if not ref or ref in seen:
                continue
            seen.add(ref)
            dedup.append(ref)
        refs = dedup[:12]
    now = _now_iso()
    assets: list[BuilderAsset] = []

    if graph_results:
        answer_type = str(graph_results.get("answer_type", "none"))
        result_obj = graph_results.get("results", {})

        if answer_type == "character_context" and isinstance(result_obj, dict):
            character = str(result_obj.get("character", "未命名角色")).strip() or "未命名角色"
            assets.append(
                _make_asset(
                    asset_type="character_card",
                    title=f"{character} 角色卡",
                    summary=f"角色 {character} 的当前关系上下文（draft）。",
                    query=query,
                    refs=refs,
                    now=now,
                    metadata={"character": character, "graph_answer_type": answer_type},
                )
            )

        if answer_type in {"relationship_between", "faction_context"}:
            assets.append(
                _make_asset(
                    asset_type="relationship_card",
                    title=f"关系卡：{answer_type}",
                    summary="从本轮图检索结果沉淀的关系结构（draft）。",
                    query=query,
                    refs=refs,
                    now=now,
                    metadata={"graph_answer_type": answer_type, "graph_results": result_obj},
                )
            )

    if any(hint in query for hint in EVENT_HINTS):
        assets.append(
            _make_asset(
                asset_type="event_card",
                title="事件卡（草稿）",
                summary="本轮问题包含事件/行动信号，建议补齐时间点、参与者和结果。",
                query=query,
                refs=refs,
                now=now,
            )
        )

    if any(hint in query for hint in FORESHADOWING_HINTS):
        assets.append(
            _make_asset(
                asset_type="foreshadowing_item",
                title="伏笔条目（待回收）",
                summary="记录本轮提及的伏笔/暗示，后续在 canon 中确认回收位置。",
                query=query,
                refs=refs,
                now=now,
            )
        )

    if any(hint in query for hint in SYSTEMS_HINTS):
        assets.append(
            _make_asset(
                asset_type="gameplay_hook",
                title="玩法钩子（草稿）",
                summary="从本轮问题沉淀一个可执行的玩法互动切入点。",
                query=query,
                refs=refs,
                now=now,
            )
        )

    assets.append(
        _make_asset(
            asset_type="open_question",
            title="待确认问题",
            summary=f"{query}（后续补 canon 证据与结论）",
            query=query,
            refs=refs,
            now=now,
            metadata={"published_refs_used": len(published_asset_refs or [])},
        )
    )

    return assets


def _safe_slug(text: str) -> str:
    normalized = SAFE_FILE_RE.sub("_", text.strip()).strip("_")
    return normalized[:60] or "untitled"


def persist_builder_assets(
    assets: list[BuilderAsset],
    *,
    root: Path | str = Path("data/workbench/draft"),
) -> list[dict[str, Any]]:
    """Persist assets to local draft directories and return saved metadata."""

    base = Path(root)
    saved: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for idx, asset in enumerate(assets, start=1):
        folder_name = ASSET_DIR_MAP.get(asset.asset_type)
        if not folder_name:
            continue

        out_dir = base / folder_name
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{ts}_{idx:02d}_{asset.asset_id}_{_safe_slug(asset.title)}.json"
        file_path = out_dir / filename
        file_path.write_text(json.dumps(asset.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

        saved.append(
            {
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "title": asset.title,
                "path": str(file_path),
                "generated_at": asset.generated_at,
                "status": asset.status,
            }
        )

    return saved


def load_asset(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "asset_type" not in data and "type" in data:
        data["asset_type"] = data["type"]
    return data


def save_asset(path: Path | str, payload: dict[str, Any]) -> None:
    payload = dict(payload)
    if "asset_type" not in payload and "type" in payload:
        payload["asset_type"] = payload["type"]
    payload["type"] = payload.get("asset_type", payload.get("type", "unknown"))
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def list_draft_assets(*, root: Path | str = Path("data/workbench")) -> list[dict[str, Any]]:
    base = Path(root) / "draft"
    if not base.exists():
        return []
    assets: list[dict[str, Any]] = []
    for path in sorted(base.rglob("*.json")):
        payload = load_asset(path)
        payload["path"] = str(path)
        if payload.get("status", "draft") == "draft":
            assets.append(payload)
    return assets


def review_asset(
    asset_path: Path | str,
    *,
    status: str,
    note: str | None = None,
) -> dict[str, Any]:
    if status not in {"approved", "rejected"}:
        raise ValueError("review status must be approved or rejected")
    path = Path(asset_path)
    payload = load_asset(path)
    if payload.get("status") == "published":
        raise ValueError("published asset cannot be reviewed again")
    payload["status"] = status
    payload["reviewed_at"] = _now_iso()
    payload["review_note"] = note or ""
    save_asset(path, payload)
    return payload


def approve_asset(asset_path: Path | str, note: str | None = None) -> dict[str, Any]:
    return review_asset(asset_path, status="approved", note=note)


def reject_asset(asset_path: Path | str, note: str | None = None) -> dict[str, Any]:
    return review_asset(asset_path, status="rejected", note=note)


def publish_asset(
    asset_path: Path | str,
    *,
    workbench_root: Path | str = Path("data/workbench"),
) -> dict[str, Any]:
    path = Path(asset_path)
    payload = load_asset(path)
    status = payload.get("status", "draft")
    if status != "approved":
        raise ValueError("only approved assets can be published")

    asset_type = payload.get("asset_type", payload.get("type", ""))
    folder = ASSET_DIR_MAP.get(asset_type)
    if not folder:
        raise ValueError(f"unknown asset_type: {asset_type}")

    published_root = Path(workbench_root) / "published" / folder
    published_root.mkdir(parents=True, exist_ok=True)
    filename = f"{payload.get('asset_id', _new_asset_id(asset_type))}_{_safe_slug(payload.get('title', 'untitled'))}.json"
    published_path = published_root / filename

    payload["status"] = "published"
    payload["published_at"] = _now_iso()
    payload["published_path"] = str(published_path)
    save_asset(published_path, payload)
    save_asset(path, payload)
    return payload
