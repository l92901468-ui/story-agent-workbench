"""Load and query published workbench assets as runtime context (stage-7D)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ASSET_TYPES = {
    "character_card",
    "relationship_card",
    "event_card",
    "open_question",
    "foreshadowing_item",
    "gameplay_hook",
}


def load_published_assets(
    *,
    root: Path | str = Path("data/workbench/published"),
) -> list[dict[str, Any]]:
    """Load published JSON assets only (draft assets are intentionally ignored)."""

    base = Path(root)
    if not base.exists():
        return []

    assets: list[dict[str, Any]] = []
    for path in sorted(base.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        asset_type = payload.get("asset_type", payload.get("type", ""))
        status = payload.get("status", "published")
        if asset_type not in ASSET_TYPES:
            continue
        if status != "published":
            continue
        payload["asset_type"] = asset_type
        payload["path"] = str(path)
        assets.append(payload)

    return assets


def build_runtime_asset_context(assets: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, list[dict[str, Any]]] = {key: [] for key in ASSET_TYPES}
    for asset in assets:
        by_type.setdefault(asset["asset_type"], []).append(asset)
    return {
        "counts": {k: len(v) for k, v in by_type.items()},
        "by_type": by_type,
        "all": assets,
    }


def _extract_query_terms(query: str) -> list[str]:
    terms = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", query)
    cjk_runs = re.findall(r"[\u4e00-\u9fff]{2,}", query)
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
    return unique


def find_relevant_published_assets(
    query: str,
    runtime_context: dict[str, Any],
    *,
    max_items: int = 3,
) -> list[dict[str, Any]]:
    terms = _extract_query_terms(query)
    if not terms:
        return []

    matched: list[dict[str, Any]] = []
    for asset in runtime_context.get("all", []):
        haystack = " ".join(
            [
                str(asset.get("title", "")),
                str(asset.get("summary", "")),
                str(asset.get("source_query", "")),
                json.dumps(asset.get("metadata", {}), ensure_ascii=False),
            ]
        )
        score = sum(1 for t in terms if t and t in haystack)
        if score <= 0:
            continue
        matched.append(
            {
                "asset_id": asset.get("asset_id", ""),
                "asset_type": asset.get("asset_type", ""),
                "title": asset.get("title", ""),
                "path": asset.get("path", ""),
                "score": score,
            }
        )

    matched.sort(key=lambda x: x["score"], reverse=True)
    return matched[:max_items]
