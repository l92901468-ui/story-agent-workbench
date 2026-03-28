"""Minimal ingest package for stage-2 text loading and chunking."""

from .chunker import chunk_text
from .folder_import import import_project_folder
from .loader import TextDocument, discover_text_documents, load_text_documents
from .project_importer import import_project_documents, run_import_checks

__all__ = [
    "TextDocument",
    "discover_text_documents",
    "load_text_documents",
    "chunk_text",
    "import_project_folder",
    "import_project_documents",
    "run_import_checks",
]
