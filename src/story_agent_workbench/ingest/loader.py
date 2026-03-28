"""Stage-2 minimal loader for .txt/.md files under data/samples."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
from typing import Iterable

SUPPORTED_SUFFIXES = {".txt", ".md", ".docx", ".doc"}
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
        text = read_text_file(file_path)
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


def _extract_docx_text(path: Path) -> str:
    """Extract basic text from .docx without external dependencies."""

    with ZipFile(path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")

    xml_text = xml_bytes.decode("utf-8", errors="ignore")
    # Remove tags and keep spacing between paragraphs/runs.
    plain = xml_text.replace("</w:p>", "\n").replace("</w:tr>", "\n")
    plain = plain.replace("</w:tab>", "\t").replace("</w:t>", "")
    out: list[str] = []
    in_tag = False
    for ch in plain:
        if ch == "<":
            in_tag = True
            continue
        if ch == ">":
            in_tag = False
            continue
        if not in_tag:
            out.append(ch)
    return "".join(out).strip()


def _extract_doc_text(path: Path) -> str:
    """Best-effort text extraction for legacy .doc binary files."""

    raw = path.read_bytes()
    # Extract printable bytes as a rough fallback. This is not perfect, but avoids extra dependencies.
    chars: list[str] = []
    for b in raw:
        if 32 <= b <= 126 or b in (9, 10, 13):
            chars.append(chr(b))
        elif b >= 160:
            chars.append(chr(b))
        else:
            chars.append(" ")
    text = "".join(chars)
    # Collapse noisy whitespace.
    return " ".join(text.split())


def read_text_file(path: Path | str) -> str:
    """Read supported text-like files (.txt/.md/.docx/.doc) as plain text."""

    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return file_path.read_text(encoding="utf-8")
    if suffix == ".docx":
        return _extract_docx_text(file_path)
    if suffix == ".doc":
        return _extract_doc_text(file_path)
    raise ValueError(f"unsupported file type: {suffix}")


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
