"""Schema definitions for stage-4 minimal structured registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Character:
    id: str
    name: str
    source: str
    description: str = ""


@dataclass
class Faction:
    id: str
    name: str
    source: str
    description: str = ""


@dataclass
class Location:
    id: str
    name: str
    source: str
    description: str = ""


@dataclass
class Event:
    id: str
    name: str
    source: str
    description: str = ""


@dataclass
class TimelineAnchor:
    id: str
    label: str
    source: str
    description: str = ""


@dataclass
class Relationship:
    id: str
    source_entity: str
    target_entity: str
    relation_type: str
    source: str
    evidence: str = ""


@dataclass
class Alias:
    id: str
    canonical_name: str
    alias: str
    source: str


@dataclass
class Registry:
    characters: list[Character] = field(default_factory=list)
    factions: list[Faction] = field(default_factory=list)
    locations: list[Location] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    timeline_anchors: list[TimelineAnchor] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    aliases: list[Alias] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "characters": [asdict(item) for item in self.characters],
            "factions": [asdict(item) for item in self.factions],
            "locations": [asdict(item) for item in self.locations],
            "events": [asdict(item) for item in self.events],
            "timeline_anchors": [asdict(item) for item in self.timeline_anchors],
            "relationships": [asdict(item) for item in self.relationships],
            "aliases": [asdict(item) for item in self.aliases],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Registry":
        return cls(
            characters=[Character(**x) for x in data.get("characters", [])],
            factions=[Faction(**x) for x in data.get("factions", [])],
            locations=[Location(**x) for x in data.get("locations", [])],
            events=[Event(**x) for x in data.get("events", [])],
            timeline_anchors=[TimelineAnchor(**x) for x in data.get("timeline_anchors", [])],
            relationships=[Relationship(**x) for x in data.get("relationships", [])],
            aliases=[Alias(**x) for x in data.get("aliases", [])],
        )
