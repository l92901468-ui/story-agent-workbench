"""Stage-3 minimal text retrieval based on stage-2 chunks."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from story_agent_workbench.ingest import chunk_text, load_text_documents
from story_agent_workbench.ingest.loader import read_text_file

TOKEN_SPLIT_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


@dataclass(frozen=True)
class RetrievalConfig:
    """Configuration for minimal text retrieval."""

    data_root: Path = Path("data/samples")
    chunk_size: int = 300
    overlap: int = 40
    extra_files: tuple[Path, ...] = ()
    extra_layer: str = "test_input"
    index_path: Path = Path("data/workbench/index/text_index.json")
    rebuild_index: bool = False


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
            text = read_text_file(path)
        except (ValueError, OSError, KeyError, RuntimeError):
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


def _vectorize_text(text: str) -> dict[str, float]:
    tokens = tokenize(text)
    if not tokens:
        return {}
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = float(len(tokens))
    return {k: v / total for k, v in counts.items()}


def _cosine_sim(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for k, va in a.items():
        vb = b.get(k)
        if vb is not None:
            dot += va * vb
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _load_persistent_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        return {"chunks": []}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"chunks": []}
    if not isinstance(data, dict):
        return {"chunks": []}
    chunks = data.get("chunks", [])
    if not isinstance(chunks, list):
        chunks = []
    return {"chunks": chunks}


def _save_persistent_index(index_path: Path, chunks: list[dict[str, Any]]) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"chunks": chunks}
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _upsert_chunks_to_index(index_data: dict[str, Any], chunks: list[dict[str, Any]]) -> tuple[int, int]:
    existing = index_data.get("chunks", [])
    by_id: dict[str, dict[str, Any]] = {}
    for item in existing:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("chunk_id", "")).strip()
        if cid:
            by_id[cid] = item

    inserted = 0
    updated = 0
    for chunk in chunks:
        cid = str(chunk.get("chunk_id", "")).strip()
        if not cid:
            continue
        item = {
            "chunk_id": cid,
            "source": chunk.get("source", ""),
            "layer": chunk.get("layer", ""),
            "text": chunk.get("text", ""),
            "vector": _vectorize_text(str(chunk.get("text", ""))),
        }
        if cid in by_id:
            updated += 1
        else:
            inserted += 1
        by_id[cid] = item

    merged = list(by_id.values())
    index_data["chunks"] = merged
    return inserted, updated


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
    index_data = _load_persistent_index(config.index_path)
    if config.rebuild_index:
        index_data = {"chunks": []}

    inserted, updated = _upsert_chunks_to_index(index_data, chunks)
    _save_persistent_index(config.index_path, index_data.get("chunks", []))

    indexed_chunks = index_data.get("chunks", [])
    query_vector = _vectorize_text(query)

    scored_results: list[dict[str, Any]] = []
    for chunk in indexed_chunks:
        lexical_score = score_chunk(query, str(chunk.get("text", "")))
        vector_score = _cosine_sim(query_vector, chunk.get("vector", {}))
        score = lexical_score + vector_score
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
            "total_chunks": len(indexed_chunks),
            "matched_chunks": len(scored_results),
            "index_path": str(config.index_path),
            "index_chunks_inserted": inserted,
            "index_chunks_updated": updated,
            **getattr(build_chunks, "last_build_stats", {}),
        },
    }
