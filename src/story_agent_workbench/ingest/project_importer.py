"""Stage-8A minimal project import pipeline for real project directories."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .loader import SUPPORTED_SUFFIXES

KNOWN_LAYERS = ("canon", "draft", "reference")


@dataclass
class ImportedDocument:
    source: str
    layer: str
    project_id: str
    doc_type: str
    chapter: str | None
    scene: str | None
    characters: list[str]
    timeline_hint: str | None
    text_length: int
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def project_root(project_id: str, projects_root: Path | str = Path("projects")) -> Path:
    return Path(projects_root) / project_id


def _infer_doc_type(path: Path) -> str:
    stem = path.stem.lower()
    if "chapter" in stem:
        return "chapter"
    if "scene" in stem:
        return "scene"
    if "character" in stem:
        return "character_note"
    if "event" in stem:
        return "event_note"
    return "note"


def _infer_chapter(path: Path) -> str | None:
    m = re.search(r"chapter[_-]?(\d+)", path.stem.lower())
    return m.group(1) if m else None


def _infer_scene(path: Path) -> str | None:
    m = re.search(r"scene[_-]?(\d+)", path.stem.lower())
    return m.group(1) if m else None


def _extract_optional_metadata(text: str) -> tuple[list[str], str | None]:
    characters: list[str] = []
    timeline_hint: str | None = None
    for line in text.splitlines()[:20]:
        normalized = line.strip()
        lower = normalized.lower()
        if lower.startswith("characters:") or normalized.startswith("角色:"):
            raw = normalized.split(":", 1)[1] if ":" in normalized else ""
            characters = [item.strip() for item in re.split(r"[，,;/]", raw) if item.strip()]
        if lower.startswith("timeline:") or normalized.startswith("时间:"):
            timeline_hint = normalized.split(":", 1)[1].strip() if ":" in normalized else None
    return characters, timeline_hint


def _discover_project_docs(root: Path) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for layer in KNOWN_LAYERS:
        layer_root = root / layer
        if not layer_root.exists():
            continue
        for path in sorted(layer_root.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
                files.append((layer, path))
    return files


def import_project_documents(
    *,
    project_id: str,
    projects_root: Path | str = Path("projects"),
) -> dict[str, Any]:
    root = project_root(project_id, projects_root)
    docs: list[ImportedDocument] = []

    for layer, path in _discover_project_docs(root):
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(root))
        chars, timeline_hint = _extract_optional_metadata(text)
        doc = ImportedDocument(
            source=rel,
            layer=layer,
            project_id=project_id,
            doc_type=_infer_doc_type(path),
            chapter=_infer_chapter(path),
            scene=_infer_scene(path),
            characters=chars,
            timeline_hint=timeline_hint,
            text_length=len(text),
            content_hash=hashlib.sha1(text.encode("utf-8")).hexdigest(),
        )
        docs.append(doc)

    checks = run_import_checks(docs)
    report = {
        "project_id": project_id,
        "project_root": str(root),
        "documents": [doc.to_dict() for doc in docs],
        "checks": checks,
        "stats": {
            "total_docs": len(docs),
            "by_layer": {
                layer: len([doc for doc in docs if doc.layer == layer]) for layer in KNOWN_LAYERS
            },
        },
    }

    wb = root / "workbench"
    wb.mkdir(parents=True, exist_ok=True)
    (wb / "import_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_import_checks(documents: list[ImportedDocument]) -> dict[str, list[str]]:
    warnings: dict[str, list[str]] = {
        "empty_documents": [],
        "duplicate_filenames": [],
        "duplicate_content": [],
        "missing_layer": [],
        "too_short": [],
        "too_long": [],
        "character_alias_conflicts": [],
    }

    name_map: dict[str, list[str]] = {}
    hash_map: dict[str, list[str]] = {}
    normalized_names: dict[str, set[str]] = {}

    for doc in documents:
        filename = Path(doc.source).name
        name_map.setdefault(filename, []).append(doc.source)
        hash_map.setdefault(doc.content_hash, []).append(doc.source)

        if doc.text_length == 0:
            warnings["empty_documents"].append(doc.source)
        if doc.layer not in KNOWN_LAYERS:
            warnings["missing_layer"].append(doc.source)
        if doc.text_length < 30:
            warnings["too_short"].append(doc.source)
        if doc.text_length > 20000:
            warnings["too_long"].append(doc.source)

        for name in doc.characters:
            key = re.sub(r"[\W_]+", "", name).lower()
            normalized_names.setdefault(key, set()).add(name)

    for name, paths in name_map.items():
        if len(paths) > 1:
            warnings["duplicate_filenames"].append(f"{name}: {paths}")
    for digest, paths in hash_map.items():
        if len(paths) > 1:
            warnings["duplicate_content"].append(f"{digest[:8]}: {paths}")
    for key, forms in normalized_names.items():
        if len(forms) > 1:
            warnings["character_alias_conflicts"].append(f"{key}: {sorted(forms)}")

    return warnings
