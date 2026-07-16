"""
Splits every included document in processed_text/ into retrieval-sized chunks and
tags each one with citation metadata (doc_name, status, effective_date, type,
parent_doc, regime, chapter, para), writing the result to chunked/chunks.jsonl.

"Included" means config/document_manifest.csv has include_in_index != "no" for
that row - this excludes the three near-duplicate DAP 2020 copies (see the
manifest's notes column for why).

Chunking groups consecutive whole paragraphs (split on blank lines) up to
TARGET_CHUNK_CHARS, only splitting a single paragraph further if it alone
exceeds that size - this keeps each chunk aligned to real paragraph boundaries
instead of cutting mid-sentence.

Chapter and paragraph numbers are detected with two regexes while scanning
paragraphs in order, and each chunk is stamped with whatever was most recently
seen at the point its first paragraph starts:
  - CHAPTER_RE matches a bare chapter heading, e.g. "CHAPTER 1" (DPM 2025) or
    "CHAPTER I" (DAP 2020 / DPP 2016).
  - PARA_RE matches a paragraph number at the start of a line, e.g. "1.1.1 This
    Manual..." (DPM-style) or "5. Priority of..." (DAP-style).
Short amendment letters mostly have no CHAPTER match (chapter stays blank) and
may pick up a numbered list item as "para", which is an acceptable proxy for
this pass rather than a promise of full accuracy - see docs/01-technical-brief.md
for the known Table-of-Contents rough edge and other limitations.

Run it from the project root with:
    .venv\\Scripts\\python.exe scripts\\chunk_documents.py
"""

import json
import re
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "processed_text"
MANIFEST_PATH = PROJECT_ROOT / "config" / "document_manifest.csv"
OUTPUT_PATH = PROJECT_ROOT / "chunked" / "chunks.jsonl"

TARGET_CHUNK_CHARS = 1500

CHAPTER_RE = re.compile(r"^CHAPTER\s+([IVXLCDM]+|\d+)\b")
PARA_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){0,3})\.?\s+\S")


def split_into_paragraphs(text: str) -> list[str]:
    raw_paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in raw_paragraphs if p.strip()]


def split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]
    pieces = []
    start = 0
    while start < len(paragraph):
        pieces.append(paragraph[start : start + max_chars])
        start += max_chars
    return pieces


def group_paragraphs_into_chunks(paragraphs: list[str]) -> list[dict]:
    """Returns a list of {"text", "chapter", "para"} dicts, one per chunk."""
    chunks = []
    current_chapter = None
    current_para = None

    buffer_paragraphs: list[str] = []
    buffer_chapter = None
    buffer_para = None
    buffer_len = 0

    def flush():
        nonlocal buffer_paragraphs, buffer_chapter, buffer_para, buffer_len
        if buffer_paragraphs:
            chunks.append(
                {
                    "text": "\n\n".join(buffer_paragraphs),
                    "chapter": buffer_chapter,
                    "para": buffer_para,
                }
            )
        buffer_paragraphs = []
        buffer_chapter = None
        buffer_para = None
        buffer_len = 0

    for paragraph in paragraphs:
        chapter_match = CHAPTER_RE.match(paragraph)
        if chapter_match:
            current_chapter = chapter_match.group(1)
        para_match = PARA_RE.match(paragraph)
        if para_match:
            current_para = para_match.group(1)

        for piece in split_long_paragraph(paragraph, TARGET_CHUNK_CHARS):
            if not buffer_paragraphs:
                buffer_chapter = current_chapter
                buffer_para = current_para

            if buffer_len + len(piece) > TARGET_CHUNK_CHARS and buffer_paragraphs:
                flush()
                buffer_chapter = current_chapter
                buffer_para = current_para

            buffer_paragraphs.append(piece)
            buffer_len += len(piece)

    flush()
    return chunks


def chunk_file(md_path: Path) -> list[dict]:
    text = md_path.read_text(encoding="utf-8")
    paragraphs = split_into_paragraphs(text)
    return group_paragraphs_into_chunks(paragraphs)


def main() -> None:
    manifest = pd.read_csv(MANIFEST_PATH)
    included = manifest[manifest["include_in_index"].fillna("yes") != "no"]
    excluded_count = len(manifest) - len(included)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0
    missing_chapter_or_para = 0
    per_file_counts = []

    with OUTPUT_PATH.open("w", encoding="utf-8") as out_f:
        for _, row in included.iterrows():
            relative_path = Path(row["filename"]).with_suffix(".md")
            md_path = PROCESSED_DIR / relative_path
            if not md_path.exists():
                print(f"WARNING: no processed_text file for {row['filename']} - skipped")
                continue

            chunks = chunk_file(md_path)
            for i, chunk in enumerate(chunks):
                record = {
                    "doc_name": row["doc_name"],
                    "status": row["status"],
                    "effective_date": None if pd.isna(row["effective_date"]) else row["effective_date"],
                    "type": row["type"],
                    "parent_doc": None if pd.isna(row["parent_doc"]) else row["parent_doc"],
                    "regime": row["regime"],
                    "chapter": chunk["chapter"],
                    "para": chunk["para"],
                    "source_file": row["filename"],
                    "chunk_index": i,
                    "text": chunk["text"],
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1
                if not chunk["chapter"] and not chunk["para"]:
                    missing_chapter_or_para += 1

            per_file_counts.append((row["filename"], len(chunks)))

    print(f"Included {len(included)}/{len(manifest)} manifest rows ({excluded_count} excluded).\n")
    for filename, count in per_file_counts:
        print(f"  {count:4d} chunks  {filename}")
    print(f"\nTotal chunks: {total_chunks}")
    print(f"Chunks with neither chapter nor para detected: {missing_chapter_or_para}")
    print(f"Written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
