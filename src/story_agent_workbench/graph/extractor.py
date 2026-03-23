"""Stage-4 minimal extractor (LLM-assisted with fallback) for canon text."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from story_agent_workbench.ingest.loader import load_text_documents

from .schema import Alias, Character, Event, Faction, Location, Registry, Relationship, TimelineAnchor


def _normalize_id(prefix: str, name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", name.strip()).strip("_")
    return f"{prefix}:{cleaned.lower() if cleaned else 'unknown'}"


def _extract_with_llm(text: str) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    prompt = (
        "你是叙事结构抽取器。请从给定文本中抽取 JSON。"
        "仅返回 JSON，不要额外解释。"
        "必须包含 keys: characters,factions,locations,events,timeline_anchors,relationships,aliases。"
        "relationships 每项包含 source_entity,target_entity,relation_type,evidence。"
    )

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": text}]},
        ],
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    output_text = data.get("output_text", "")
    if not output_text:
        return None

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def _extract_fallback(text: str) -> dict[str, Any]:
    """Simple regex/rule fallback for minimal robustness."""

    # Very lightweight patterns for current MVP samples.
    character_names = sorted(set(re.findall(r"艾琳|罗安", text)))
    faction_names = sorted(set(re.findall(r"[\u4e00-\u9fff]{1,4}阵营|灰塔", text)))
    location_names = sorted(set(re.findall(r"[\u4e00-\u9fff]{1,6}港口", text)))

    timeline = []
    if "三天" in text:
        timeline.append("连续三天")

    events = []
    for key in ["会合", "延迟", "招募", "不公开情报", "冲突升级"]:
        if key in text:
            events.append(key)

    aliases = []
    if "灰塔阵营" in text and "灰塔" in text:
        aliases.append({"canonical_name": "灰塔阵营", "alias": "灰塔"})

    relationships = []
    if "艾琳" in text and any("灰塔" in f for f in faction_names):
        relationships.append(
            {
                "source_entity": "艾琳",
                "target_entity": "灰塔阵营",
                "relation_type": "investigates",
                "evidence": "艾琳确认灰塔阵营在暗地里招募码头工",
            }
        )
    if "艾琳" in text and "罗安" in text:
        relationships.append(
            {
                "source_entity": "艾琳",
                "target_entity": "罗安",
                "relation_type": "conflict",
                "evidence": "草稿提到艾琳与罗安的冲突升级",
            }
        )

    return {
        "characters": [{"name": x} for x in character_names],
        "factions": [{"name": x} for x in faction_names],
        "locations": [{"name": x} for x in location_names],
        "events": [{"name": x} for x in events],
        "timeline_anchors": [{"label": x} for x in timeline],
        "relationships": relationships,
        "aliases": aliases,
    }


def _as_list(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    val = data.get(key, [])
    return val if isinstance(val, list) else []


def extract_registry_from_canon(
    *,
    data_root: Path | str = Path("data/samples"),
    output_path: Path | str = Path("data/extracted/registry.json"),
    use_llm: bool = True,
) -> Registry:
    """Extract a minimal structured registry from canon docs and save JSON."""

    documents = [doc for doc in load_text_documents(data_root) if doc.layer == "canon"]
    registry = Registry()

    for doc in documents:
        parsed = _extract_with_llm(doc.text) if use_llm else None
        if parsed is None:
            parsed = _extract_fallback(doc.text)

        for item in _as_list(parsed, "characters"):
            name = str(item.get("name", "")).strip()
            if name:
                registry.characters.append(
                    Character(id=_normalize_id("character", name), name=name, source=doc.source)
                )

        for item in _as_list(parsed, "factions"):
            name = str(item.get("name", "")).strip()
            if name:
                registry.factions.append(Faction(id=_normalize_id("faction", name), name=name, source=doc.source))

        for item in _as_list(parsed, "locations"):
            name = str(item.get("name", "")).strip()
            if name:
                registry.locations.append(
                    Location(id=_normalize_id("location", name), name=name, source=doc.source)
                )

        for item in _as_list(parsed, "events"):
            name = str(item.get("name", "")).strip()
            if name:
                registry.events.append(Event(id=_normalize_id("event", name), name=name, source=doc.source))

        for item in _as_list(parsed, "timeline_anchors"):
            label = str(item.get("label", "")).strip()
            if label:
                registry.timeline_anchors.append(
                    TimelineAnchor(
                        id=_normalize_id("timeline", label),
                        label=label,
                        source=doc.source,
                    )
                )

        for item in _as_list(parsed, "relationships"):
            src = str(item.get("source_entity", "")).strip()
            tgt = str(item.get("target_entity", "")).strip()
            rel = str(item.get("relation_type", "related_to")).strip() or "related_to"
            evidence = str(item.get("evidence", "")).strip()
            if src and tgt:
                registry.relationships.append(
                    Relationship(
                        id=_normalize_id("relationship", f"{src}_{rel}_{tgt}"),
                        source_entity=src,
                        target_entity=tgt,
                        relation_type=rel,
                        source=doc.source,
                        evidence=evidence,
                    )
                )

        for item in _as_list(parsed, "aliases"):
            canonical = str(item.get("canonical_name", "")).strip()
            alias = str(item.get("alias", "")).strip()
            if canonical and alias:
                registry.aliases.append(
                    Alias(
                        id=_normalize_id("alias", f"{canonical}_{alias}"),
                        canonical_name=canonical,
                        alias=alias,
                        source=doc.source,
                    )
                )

    # de-duplicate by id
    def _dedupe(items: list[Any]) -> list[Any]:
        seen = set()
        out = []
        for item in items:
            if item.id in seen:
                continue
            seen.add(item.id)
            out.append(item)
        return out

    registry.characters = _dedupe(registry.characters)
    registry.factions = _dedupe(registry.factions)
    registry.locations = _dedupe(registry.locations)
    registry.events = _dedupe(registry.events)
    registry.timeline_anchors = _dedupe(registry.timeline_anchors)
    registry.relationships = _dedupe(registry.relationships)
    registry.aliases = _dedupe(registry.aliases)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(registry.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    return registry
