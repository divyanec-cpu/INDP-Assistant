"""
Shared helpers for turning chunked/chunks.jsonl records into llama-index
TextNode objects, used by both build_vector_index.py (to embed chunks) and
hybrid_retrieve.py (to build the BM25 index over the same chunks).
"""

import hashlib
import json
from pathlib import Path

from llama_index.core.schema import TextNode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHUNKS_PATH = PROJECT_ROOT / "chunked" / "chunks.jsonl"

METADATA_FIELDS = [
    "doc_name",
    "status",
    "effective_date",
    "type",
    "parent_doc",
    "regime",
    "chapter",
    "para",
    "source_file",
    "chunk_index",
]


def load_chunks() -> list[dict]:
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def chunk_id(record: dict) -> str:
    key = f"{record['source_file']}::{record['chunk_index']}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def to_text_node(record: dict) -> TextNode:
    metadata = {}
    for field in METADATA_FIELDS:
        value = record.get(field)
        metadata[field] = "" if value is None else value
    return TextNode(id_=chunk_id(record), text=record["text"], metadata=metadata)


def load_all_nodes() -> list[TextNode]:
    return [to_text_node(r) for r in load_chunks()]
