"""Minimal ingest package for stage-2 text loading and chunking."""

from .chunker import chunk_text
from .loader import TextDocument, discover_text_documents, load_text_documents

__all__ = [
    "TextDocument",
    "discover_text_documents",
    "load_text_documents",
    "chunk_text",
]
