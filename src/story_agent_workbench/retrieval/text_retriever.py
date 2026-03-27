"""Stage-3 minimal text retrieval based on stage-2 chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from story_agent_workbench.ingest import chunk_text, load_text_documents

TOKEN_SPLIT_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


@dataclass(frozen=True)
class RetrievalConfig:
    """Configuration for minimal text retrieval."""

    data_root: Path = Path("data/samples")
    chunk_size: int = 300
    overlap: int = 40
    extra_files: tuple[Path, ...] = ()
    extra_layer: str = "test_input"


def tokenize(text: str) -> list[str]:
    """Tokenize text with a lightweight regex-based splitter."""

    parts = TOKEN_SPLIT_RE.split(text.lower())
    return [p for p in parts if p]


def score_chunk(query: str, chunk_text_value: str) -> float:
    """Compute a very simple relevance score.

    Score design (intentionally simple):
    - +1 for each unique query token appearing in chunk text
    - +1.5 bonus if full query substring appears in chunk text
    """

    normalized_chunk = chunk_text_value.lower()
    query_tokens = sorted(set(tokenize(query)))

    if not query_tokens:
        return 0.0

    token_hits = sum(1 for token in query_tokens if token in normalized_chunk)
    full_query_bonus = 1.5 if query.strip().lower() in normalized_chunk else 0.0

    return float(token_hits) + full_query_bonus


def build_chunks(config: RetrievalConfig) -> list[dict[str, Any]]:
    """Load documents and convert them into retrieval chunks."""

    documents = load_text_documents(config.data_root)
    all_chunks: list[dict[str, Any]] = []
    loaded_extra_files = 0
    skipped_extra_files = 0

    for doc in documents:
        all_chunks.extend(
            chunk_text(
                text=doc.text,
                source=doc.source,
                layer=doc.layer,
                chunk_size=config.chunk_size,
                overlap=config.overlap,
            )
        )

    for file_path in config.extra_files:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            skipped_extra_files += 1
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            skipped_extra_files += 1
            continue

        loaded_extra_files += 1
        all_chunks.extend(
            chunk_text(
                text=text,
                source=str(path),
                layer=config.extra_layer,
                chunk_size=config.chunk_size,
                overlap=config.overlap,
            )
        )

    build_chunks.last_build_stats = {
        "extra_files_requested": len(config.extra_files),
        "extra_files_loaded": loaded_extra_files,
        "extra_files_skipped": skipped_extra_files,
    }

    return all_chunks


def retrieve_text(
    *,
    query: str,
    top_k: int = 3,
    config: RetrievalConfig | None = None,
) -> dict[str, Any]:
    """Retrieve top_k chunks for a query.

    Returns a dict containing:
    - query, top_k
    - results: list of {source, chunk_id, layer, text, score}
    - evidence: list of short human-readable evidence lines
    """

    if config is None:
        config = RetrievalConfig()

    chunks = build_chunks(config)

    scored_results: list[dict[str, Any]] = []
    for chunk in chunks:
        score = score_chunk(query, chunk["text"])
        if score <= 0:
            continue

        scored_results.append(
            {
                "source": chunk["source"],
                "chunk_id": chunk["chunk_id"],
                "layer": chunk["layer"],
                "text": chunk["text"],
                "score": round(score, 3),
            }
        )

    scored_results.sort(key=lambda item: item["score"], reverse=True)
    top_results = scored_results[: max(top_k, 0)]

    evidence = [
        f"[{idx}] {item['chunk_id']} | source={item['source']} | layer={item['layer']} | score={item['score']}"
        for idx, item in enumerate(top_results, start=1)
    ]

    return {
        "query": query,
        "top_k": top_k,
        "results": top_results,
        "evidence": evidence,
        "stats": {
            "total_chunks": len(chunks),
            "matched_chunks": len(scored_results),
            **getattr(build_chunks, "last_build_stats", {}),
        },
    }
