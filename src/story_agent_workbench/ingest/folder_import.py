"""Stage-8D folder import mode for no-code users."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .chunker import chunk_text
from .loader import SUPPORTED_SUFFIXES

SYSTEM_DIR_NAMES = {
    ".workbench",
    "workbench",
    "published",
    "cache",
    "logs",
    "__pycache__",
    ".git",
}
TARGET_LAYERS = ("canon", "draft", "reference")
SOURCE_DIRS = ("incoming", *TARGET_LAYERS)
WORKBENCH_SUBDIRS = (
    "chunks",
    "summaries",
    "graph",
    "assets/draft",
    "review",
    "published",
    "quality",
    "cache",
    "logs",
)


@dataclass
class ImportedRecord:
    source: str
    target_layer: str
    classified_by: str
    reason: str
    text_length: int
    chunk_count: int
    moved_to: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target_layer": self.target_layer,
            "classified_by": self.classified_by,
            "reason": self.reason,
            "text_length": self.text_length,
            "chunk_count": self.chunk_count,
            "moved_to": self.moved_to,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_project_layout(project_root: Path) -> None:
    for name in SOURCE_DIRS:
        (project_root / name).mkdir(parents=True, exist_ok=True)
    wb = project_root / ".workbench"
    for sub in WORKBENCH_SUBDIRS:
        (wb / sub).mkdir(parents=True, exist_ok=True)


def _iter_source_files(project_root: Path) -> tuple[list[tuple[str, Path]], list[str]]:
    files: list[tuple[str, Path]] = []
    skipped: list[str] = []
    for layer in SOURCE_DIRS:
        root = project_root / layer
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(project_root))
            if any(part in SYSTEM_DIR_NAMES for part in path.parts):
                skipped.append(f"{rel} (system_dir)")
                continue
            if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                skipped.append(f"{rel} (unsupported_suffix)")
                continue
            files.append((layer, path))
    return files, skipped


def _auto_classify(path: Path, text: str) -> tuple[str, str]:
    content = f"{path.name.lower()}\n{text[:1200].lower()}"

    ref_hits = [k for k in ("参考", "资料", "链接", "http", "wiki", "访谈", "设定集") if k in content]
    draft_hits = [k for k in ("草稿", "待定", "todo", "脑暴", "聊天", "临时", "想法", "版本") if k in content]
    canon_hits = [k for k in ("设定", "规则", "世界观", "角色卡", "章节", "章", "最终版") if k in content]

    if ref_hits:
        return "reference", f"reference-like keywords: {', '.join(ref_hits[:3])}"
    if draft_hits:
        return "draft", f"draft-like keywords: {', '.join(draft_hits[:3])}"
    if canon_hits:
        return "canon", f"canon-like keywords: {', '.join(canon_hits[:3])}"
    return "draft", "ambiguous incoming text; default to draft"


def _split_structured(text: str) -> tuple[list[str], str]:
    lines = [line.rstrip() for line in text.splitlines()]

    heading_blocks: list[str] = []
    if any(re.match(r"^\s{0,3}(#|第[一二三四五六七八九十\d]+[章节幕卷])", ln) for ln in lines):
        current: list[str] = []
        for ln in lines:
            if re.match(r"^\s{0,3}(#|第[一二三四五六七八九十\d]+[章节幕卷])", ln) and current:
                heading_blocks.append("\n".join(current).strip())
                current = [ln]
            else:
                current.append(ln)
        if current:
            heading_blocks.append("\n".join(current).strip())
        heading_blocks = [blk for blk in heading_blocks if len(blk) >= 40]
        if heading_blocks:
            return heading_blocks, "heading_or_chapter"

    dialogue_blocks: list[str] = []
    if any("：" in ln or ":" in ln for ln in lines):
        current = []
        for ln in lines:
            if not ln.strip():
                if current:
                    dialogue_blocks.append("\n".join(current).strip())
                    current = []
                continue
            current.append(ln)
            if len(current) >= 8:
                dialogue_blocks.append("\n".join(current).strip())
                current = []
        if current:
            dialogue_blocks.append("\n".join(current).strip())
        dialogue_blocks = [blk for blk in dialogue_blocks if len(blk) >= 40]
        if dialogue_blocks:
            return dialogue_blocks, "dialogue_or_topic"

    para_blocks = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    para_blocks = [blk for blk in para_blocks if len(blk) >= 40]
    if para_blocks:
        return para_blocks, "paragraph"

    return [], "fallback_fixed"


def _chunk_document(*, text: str, source: str, layer: str) -> tuple[list[dict[str, Any]], str]:
    structured, strategy = _split_structured(text)
    if structured:
        chunks: list[dict[str, Any]] = []
        for idx, block in enumerate(structured, start=1):
            chunks.append(
                {
                    "chunk_id": f"{source}::segment_{idx:04d}",
                    "source": source,
                    "layer": layer,
                    "text": block,
                    "chunk_strategy": strategy,
                }
            )
        return chunks, strategy

    chunks = chunk_text(text=text, source=source, layer=layer, chunk_size=350, overlap=40)
    for chunk in chunks:
        chunk["chunk_strategy"] = strategy
    return chunks, strategy


def _copy_into_layer(project_root: Path, source_path: Path, target_layer: str) -> Path:
    relative_name = source_path.name
    target_base = project_root / target_layer
    candidate = target_base / relative_name
    idx = 1
    while candidate.exists():
        candidate = target_base / f"{source_path.stem}__auto_{idx}{source_path.suffix}"
        idx += 1
    shutil.copy2(source_path, candidate)
    return candidate


def _make_summaries(records: list[ImportedRecord]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for rec in records:
        if rec.text_length == 0:
            digest = "empty document"
        elif rec.text_length < 120:
            digest = "short document, summary skipped"
        else:
            digest = f"Imported into {rec.target_layer}, chunks={rec.chunk_count}."
        summaries.append({"source": rec.source, "summary": digest, "layer": rec.target_layer})
    return summaries


def import_project_folder(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root)
    _ensure_project_layout(root)

    scanned, skipped = _iter_source_files(root)
    records: list[ImportedRecord] = []
    chunks: list[dict[str, Any]] = []
    auto_classified = 0
    moved_incoming = 0

    for src_layer, path in scanned:
        rel = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            skipped.append(f"{rel} (read_error)")
            continue

        moved_to = None
        if src_layer == "incoming":
            target_layer, reason = _auto_classify(path, text)
            classified_by = "auto"
            auto_classified += 1
            moved_path = _copy_into_layer(root, path, target_layer)
            moved_to = str(moved_path.relative_to(root))
            moved_incoming += 1
        else:
            target_layer, reason, classified_by = src_layer, "user explicit folder", "explicit"

        doc_chunks, strategy = _chunk_document(text=text, source=rel, layer=target_layer)
        for chunk in doc_chunks:
            chunk["classification_reason"] = reason
            chunk["classification_mode"] = classified_by
            chunk["chunk_strategy"] = strategy
        chunks.extend(doc_chunks)

        records.append(
            ImportedRecord(
                source=rel,
                target_layer=target_layer,
                classified_by=classified_by,
                reason=reason,
                text_length=len(text),
                chunk_count=len(doc_chunks),
                moved_to=moved_to,
            )
        )

    wb = root / ".workbench"
    chunk_file = wb / "chunks" / "chunks.jsonl"
    chunk_file.write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks),
        encoding="utf-8",
    )

    summaries = _make_summaries(records)
    (wb / "summaries" / "import_summaries.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    graph_seed = {
        "generated_at": _now_iso(),
        "from_import": True,
        "characters": [],
        "factions": [],
        "locations": [],
        "events": [],
        "timeline_anchors": [],
        "relationships": [],
        "aliases": [],
    }
    (wb / "graph" / "registry_seed.json").write_text(
        json.dumps(graph_seed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "project_root": str(root),
        "scanned_files": len(scanned),
        "auto_classified_files": auto_classified,
        "incoming_copied_to_layers": moved_incoming,
        "chunk_count": len(chunks),
        "skipped_files": skipped,
        "issues": {
            "empty_text": [r.source for r in records if r.text_length == 0],
            "too_short_text": [r.source for r in records if 0 < r.text_length < 40],
            "no_chunks": [r.source for r in records if r.chunk_count == 0],
        },
        "documents": [r.to_dict() for r in records],
        "workbench_outputs": {
            "chunks": str(chunk_file.relative_to(root)),
            "summaries": ".workbench/summaries/import_summaries.json",
            "graph_seed": ".workbench/graph/registry_seed.json",
            "report": ".workbench/logs/import_report.json",
        },
    }

    (wb / "logs" / "import_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary
