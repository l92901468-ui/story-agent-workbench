"""Stage-3 minimal text retrieval based on stage-2 chunks."""

from __future__ import annotations

import math
import re
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from story_agent_workbench.ingest import chunk_text, load_text_documents
from story_agent_workbench.ingest.loader import read_text_file

TOKEN_SPLIT_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)
UPLOAD_PRE_CHUNK_SIZE = 5000


@dataclass(frozen=True)
class RetrievalConfig:
    """Configuration for minimal text retrieval."""

    data_root: Path = Path("data/samples")
    project_id: str | None = None
    project_root: Path | None = None
    projects_root: Path = Path("projects")
    chunk_size: int = 300
    overlap: int = 40
    extra_files: tuple[Path, ...] = ()
    extra_layer: str = "test_input"
    index_path: Path = Path("data/workbench/index/text_index.json")
    rebuild_index: bool = False


def resolve_data_root(config: RetrievalConfig) -> Path:
    if config.project_root:
        return config.project_root
    if config.project_id:
        return config.projects_root / config.project_id
    return config.data_root


def resolve_index_path(config: RetrievalConfig) -> Path:
    """Resolve index path, using project-local index by default for project mode."""

    default_index = Path("data/workbench/index/text_index.json")
    if config.index_path != default_index:
        return config.index_path

    root = resolve_data_root(config)
    if config.project_root or config.project_id:
        return root / ".workbench" / "index" / "text_index.json"
    return config.index_path


def tokenize(text: str) -> list[str]:
    """Tokenize text with a lightweight regex-based splitter."""

    parts = TOKEN_SPLIT_RE.split(text.lower())
    return [p for p in parts if p]


def _pre_chunk_user_text(text: str, chunk_size: int = UPLOAD_PRE_CHUNK_SIZE) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    return [cleaned[i : i + chunk_size] for i in range(0, len(cleaned), chunk_size)]


def _llm_refine_upload_chunks(*, query_hint: str, coarse_chunks: list[str]) -> list[str] | None:
    """Use LLM to refine 5000-char coarse chunks into semantic segments."""

    api_key = os.getenv("API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    if not api_key or not coarse_chunks:
        return None

    prompt = (
        "你是文本预处理助手。输入是一组长文本分块。请把每一块继续细分成更适合检索的小段，"
        "每段尽量语义完整，不要改写原文，不要遗漏内容。"
        "只返回 JSON 数组，数组元素是字符串。"
    )
    user_payload = json.dumps({"hint": query_hint, "chunks": coarse_chunks}, ensure_ascii=False)
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "max_output_tokens": 1600,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_payload}]},
        ],
        "metadata": {"agent_role": "upload_segment_refiner"},
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    output_text = str(data.get("output_text", "")).strip()
    if not output_text:
        return None
    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None

    refined = [str(item).strip() for item in parsed if str(item).strip()]
    return refined or None


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

    root = resolve_data_root(config)
    chunk_cache = root / ".workbench" / "chunks" / "chunks.jsonl"
    if chunk_cache.exists():
        lines = chunk_cache.read_text(encoding="utf-8").splitlines()
        cached = [json.loads(line) for line in lines if line.strip()]
        if cached:
            return cached

    documents = load_text_documents(root)
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

    for asset in _load_draft_assets_for_rag(root, project_mode=bool(config.project_id or config.project_root)):
        all_chunks.extend(
            chunk_text(
                text=asset["text"],
                source=asset["source"],
                layer="draft",
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
        coarse_chunks = _pre_chunk_user_text(text, chunk_size=UPLOAD_PRE_CHUNK_SIZE)
        refined_chunks = _llm_refine_upload_chunks(query_hint=path.name, coarse_chunks=coarse_chunks)
        segments = refined_chunks if refined_chunks else coarse_chunks
        for seg_idx, segment in enumerate(segments):
            all_chunks.extend(
                chunk_text(
                    text=segment,
                    source=f"{path}#seg_{seg_idx:03d}",
                    layer=config.extra_layer,
                    chunk_size=config.chunk_size,
                    overlap=config.overlap,
                )
            )

    build_chunks.last_build_stats = {
        "extra_files_requested": len(config.extra_files),
        "extra_files_loaded": loaded_extra_files,
        "extra_files_skipped": skipped_extra_files,
        "upload_pre_chunk_size": UPLOAD_PRE_CHUNK_SIZE,
    }

    return all_chunks


def _load_draft_assets_for_rag(root: Path, *, project_mode: bool) -> list[dict[str, str]]:
    """Load draft asset JSON as additional RAG text sources."""

    candidate_dirs = []
    if project_mode:
        candidate_dirs.extend([root / "workbench" / "draft", root / ".workbench" / "assets" / "draft"])
    else:
        candidate_dirs.append(Path("data/workbench/draft"))

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for base in candidate_dirs:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.json")):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            parts = [
                str(payload.get("title", "")).strip(),
                str(payload.get("summary", "")).strip(),
                str(payload.get("source_query", "")).strip(),
                str(payload.get("review_note", "")).strip(),
            ]
            text = "\n".join([p for p in parts if p]).strip()
            if not text:
                continue
            out.append({"source": f"draft_asset::{path}", "text": text})
    return out


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
    index_path = resolve_index_path(config)
    index_data = _load_persistent_index(index_path)
    if config.rebuild_index:
        index_data = {"chunks": []}

    inserted, updated = _upsert_chunks_to_index(index_data, chunks)
    _save_persistent_index(index_path, index_data.get("chunks", []))

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
            "index_path": str(index_path),
            "index_chunks_inserted": inserted,
            "index_chunks_updated": updated,
            **getattr(build_chunks, "last_build_stats", {}),
        },
    }
