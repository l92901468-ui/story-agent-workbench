"""Stage-4 minimal graph retriever over extracted registry JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import Registry


@dataclass(frozen=True)
class GraphConfig:
    registry_path: Path = Path("data/extracted/registry.json")


def load_registry(config: GraphConfig | None = None) -> Registry:
    if config is None:
        config = GraphConfig()

    if not config.registry_path.exists():
        return Registry()

    data = json.loads(config.registry_path.read_text(encoding="utf-8"))
    return Registry.from_dict(data)


def _collect_entities(registry: Registry) -> set[str]:
    names = {item.name for item in registry.characters}
    names.update(item.name for item in registry.factions)
    names.update(item.name for item in registry.locations)
    names.update(item.name for item in registry.events)
    names.update(item.label for item in registry.timeline_anchors)
    names.update(item.alias for item in registry.aliases)
    names.update(item.canonical_name for item in registry.aliases)
    return names


def _resolve_alias(registry: Registry, name: str) -> str:
    for item in registry.aliases:
        if item.alias == name:
            return item.canonical_name
    return name


def query_relationship_between(registry: Registry, entity_a: str, entity_b: str) -> list[dict[str, Any]]:
    a = _resolve_alias(registry, entity_a)
    b = _resolve_alias(registry, entity_b)

    matches = []
    for rel in registry.relationships:
        pair = {rel.source_entity, rel.target_entity}
        if {a, b} == pair:
            matches.append(
                {
                    "source_entity": rel.source_entity,
                    "target_entity": rel.target_entity,
                    "relation_type": rel.relation_type,
                    "evidence": rel.evidence,
                    "source": rel.source,
                }
            )
    return matches


def query_character_context(registry: Registry, character_name: str) -> dict[str, Any]:
    name = _resolve_alias(registry, character_name)
    related_people = set()
    related_factions = set()
    related_events = set()
    evidence = []

    for rel in registry.relationships:
        if rel.source_entity == name or rel.target_entity == name:
            other = rel.target_entity if rel.source_entity == name else rel.source_entity
            if any(ch.name == other for ch in registry.characters):
                related_people.add(other)
            if any(f.name == other for f in registry.factions):
                related_factions.add(other)
            if any(ev.name == other for ev in registry.events):
                related_events.add(other)
            evidence.append(
                {
                    "relation_type": rel.relation_type,
                    "other": other,
                    "source": rel.source,
                    "evidence": rel.evidence,
                }
            )

    return {
        "character": name,
        "related_people": sorted(related_people),
        "related_factions": sorted(related_factions),
        "related_events": sorted(related_events),
        "evidence": evidence,
    }


def query_faction_context(registry: Registry, faction_name: str) -> dict[str, Any]:
    name = _resolve_alias(registry, faction_name)
    key_people = set()
    key_events = set()
    evidence = []

    for rel in registry.relationships:
        if rel.source_entity == name or rel.target_entity == name:
            other = rel.target_entity if rel.source_entity == name else rel.source_entity
            if any(ch.name == other for ch in registry.characters):
                key_people.add(other)
            if any(ev.name == other for ev in registry.events):
                key_events.add(other)
            evidence.append(
                {
                    "relation_type": rel.relation_type,
                    "other": other,
                    "source": rel.source,
                    "evidence": rel.evidence,
                }
            )

    return {
        "faction": name,
        "key_people": sorted(key_people),
        "key_events": sorted(key_events),
        "evidence": evidence,
    }


def retrieve_graph(query: str, config: GraphConfig | None = None) -> dict[str, Any]:
    """Retrieve minimal graph answers for global relation questions."""

    registry = load_registry(config)
    entities = sorted(_collect_entities(registry), key=len, reverse=True)
    matched_entities = [entity for entity in entities if entity and entity in query]

    result: dict[str, Any] = {
        "query": query,
        "matched_entities": matched_entities,
        "answer_type": "none",
        "results": {},
        "evidence": [],
    }

    if len(matched_entities) >= 2 and ("关系" in query or "关联" in query):
        unique_entities: list[str] = []
        seen = set()
        for ent in matched_entities:
            canonical = _resolve_alias(registry, ent)
            if canonical in seen:
                continue
            seen.add(canonical)
            unique_entities.append(canonical)
            if len(unique_entities) == 2:
                break

        if len(unique_entities) >= 2:
            a, b = unique_entities[0], unique_entities[1]
            rels = query_relationship_between(registry, a, b)
            result["answer_type"] = "relationship_between"
            result["results"] = {"entity_a": a, "entity_b": b, "relationships": rels}
            result["evidence"] = [
                f"{r['source_entity']} -> {r['target_entity']} ({r['relation_type']}) | {r['source']}"
                for r in rels
            ]
            return result

    if matched_entities:
        first = matched_entities[0]

        if "阵营" in query:
            faction_info = query_faction_context(registry, first)
            result["answer_type"] = "faction_context"
            result["results"] = faction_info
            result["evidence"] = [
                f"{item['other']} ({item['relation_type']}) | {item['source']}"
                for item in faction_info.get("evidence", [])
            ]
            return result

        character_info = query_character_context(registry, first)
        result["answer_type"] = "character_context"
        result["results"] = character_info
        result["evidence"] = [
            f"{item['other']} ({item['relation_type']}) | {item['source']}"
            for item in character_info.get("evidence", [])
        ]
        return result

    return result
