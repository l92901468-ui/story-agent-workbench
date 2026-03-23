"""Stage-2 minimal chunker (fixed size + overlap)."""

from __future__ import annotations

from typing import Any


def chunk_text(
    *,
    text: str,
    source: str,
    layer: str,
    chunk_size: int = 300,
    overlap: int = 40,
) -> list[dict[str, Any]]:
    """Split text into chunks for manual inspection.

    Each returned chunk contains:
    - chunk_id
    - source
    - layer
    - text
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    cleaned = text.strip()
    if not cleaned:
        return []

    step = chunk_size - overlap
    chunks: list[dict[str, Any]] = []
    cursor = 0
    index = 0

    while cursor < len(cleaned):
        segment = cleaned[cursor : cursor + chunk_size]
        chunks.append(
            {
                "chunk_id": f"{source}::chunk_{index:04d}",
                "source": source,
                "layer": layer,
                "text": segment,
            }
        )
        index += 1
        cursor += step

    return chunks
