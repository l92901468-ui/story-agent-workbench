"""Manual stage-2 verification script.

Usage:
    python scripts/stage2_ingest_demo.py
    python scripts/stage2_ingest_demo.py --root data/samples --chunk-size 200 --overlap 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from story_agent_workbench.ingest.chunker import chunk_text
from story_agent_workbench.ingest.loader import load_text_documents, summarize_documents


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage-2 minimal text ingest demo")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/samples"),
        help="Input directory containing .txt/.md files (default: data/samples)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=300,
        help="Chunk size in characters (default: 300)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=40,
        help="Chunk overlap in characters (default: 40)",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=5,
        help="How many chunks to preview (default: 5)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    documents = load_text_documents(args.root)
    all_chunks = []

    for doc in documents:
        chunks = chunk_text(
            text=doc.text,
            source=doc.source,
            layer=doc.layer,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
        )
        all_chunks.extend(chunks)

    print("=== Stage-2 Ingest Demo ===")
    print(f"root: {args.root}")
    print(summarize_documents(documents))
    print(f"chunks={len(all_chunks)}")

    preview_count = min(max(args.preview, 0), len(all_chunks))
    if preview_count == 0:
        print("No chunks to preview.")
        return

    print("\n--- chunk preview ---")
    for idx, chunk in enumerate(all_chunks[:preview_count], start=1):
        text_preview = chunk["text"].replace("\n", " ").strip()
        if len(text_preview) > 120:
            text_preview = text_preview[:120] + "..."

        print(
            f"[{idx}] {chunk['chunk_id']} | source={chunk['source']} | "
            f"layer={chunk['layer']} | text={text_preview}"
        )


if __name__ == "__main__":
    main()
