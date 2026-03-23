"""Stage-2 minimal loader for .txt/.md files under data/samples."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SUPPORTED_SUFFIXES = {".txt", ".md"}
KNOWN_LAYERS = {"canon", "draft", "reference"}
SYSTEM_DIR_NAMES = {".workbench", "workbench", "published", "cache", "logs", "__pycache__", ".git"}


@dataclass(frozen=True)
class TextDocument:
    """A loaded source document for chunking.

    Attributes:
        source: File path relative to the ingest root when possible.
        layer: Semantic layer derived from the path (canon/draft/reference/unknown).
        text: Full text content.
    """

    source: str
    layer: str
    text: str


def infer_layer_from_path(path: Path) -> str:
    """Infer semantic layer from path segments.

    Example:
        data/samples/canon/chapter1.md -> canon
    """

    for part in path.parts:
        lower = part.lower()
        if lower in KNOWN_LAYERS:
            return lower
    return "unknown"


def discover_text_documents(root_dir: Path | str) -> list[Path]:
    """Discover .txt/.md files recursively under root_dir."""

    root_path = Path(root_dir)
    if not root_path.exists():
        return []

    files = [
        path
        for path in root_path.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_SUFFIXES
        and not any(part in SYSTEM_DIR_NAMES for part in path.parts)
    ]
    return sorted(files)


def load_text_documents(root_dir: Path | str) -> list[TextDocument]:
    """Load all discovered text documents from root_dir."""

    root_path = Path(root_dir)
    documents: list[TextDocument] = []

    for file_path in discover_text_documents(root_path):
        text = file_path.read_text(encoding="utf-8")
        try:
            source = str(file_path.relative_to(root_path))
        except ValueError:
            source = str(file_path)

        documents.append(
            TextDocument(
                source=source,
                layer=infer_layer_from_path(file_path),
                text=text,
            )
        )

    return documents


def summarize_documents(documents: Iterable[TextDocument]) -> str:
    """Build a simple human-readable summary for manual checks."""

    counts: dict[str, int] = {}
    total_chars = 0
    for doc in documents:
        counts[doc.layer] = counts.get(doc.layer, 0) + 1
        total_chars += len(doc.text)

    parts = [f"documents={sum(counts.values())}", f"chars={total_chars}"]
    if counts:
        layer_repr = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
        parts.append(f"layers=[{layer_repr}]")

    return " | ".join(parts)
