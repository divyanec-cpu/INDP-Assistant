"""
Converts every PDF in raw_pdfs/ into a text file in processed_text/, keeping the
same folder structure (e.g. raw_pdfs/DAP_2020/DAP2020.pdf becomes
processed_text/DAP_2020/DAP2020.md).

Primary method: direct text-layer extraction via pypdfium2. This is fast, uses very
little memory, and captures complete text for any "born-digital" PDF (one that has
an actual text layer, which is true of nearly all official policy documents - even
some with scan-sounding filenames turned out to have one).

Fallback: for a PDF whose extracted text is suspiciously sparse (average under
MIN_CHARS_PER_PAGE characters per page), the script assumes it's a scanned/image-only
PDF and re-processes it with Docling's OCR pipeline instead. That path is far slower
and more memory-hungry, so it's only used when the fast path clearly didn't work -
this matters because Docling's full AI pipeline can exhaust RAM on long documents on
machines with limited memory, silently dropping most of the text on the pages it fails
on (see docs/01-technical-brief.md for how this was discovered).

Run it from the project root with:
    .venv\\Scripts\\python.exe scripts\\convert_pdfs.py

Already-converted files are skipped automatically, so it's safe to re-run after adding
new PDFs to raw_pdfs/ - only the new ones will be processed.
"""

import sys
import time
from pathlib import Path

import pypdfium2 as pdfium

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_PDFS_DIR = PROJECT_ROOT / "raw_pdfs"
PROCESSED_DIR = PROJECT_ROOT / "processed_text"

MIN_CHARS_PER_PAGE = 200  # below this average, assume the PDF is scanned and needs OCR


def find_pdfs(root: Path) -> list[Path]:
    return sorted(root.rglob("*.pdf"))


def output_path_for(pdf_path: Path) -> Path:
    relative = pdf_path.relative_to(RAW_PDFS_DIR)
    return (PROCESSED_DIR / relative).with_suffix(".md")


def extract_native_text(pdf_path: Path) -> tuple[str, float]:
    doc = pdfium.PdfDocument(str(pdf_path))
    page_texts = []
    total_chars = 0
    for page in doc:
        text = page.get_textpage().get_text_range()
        page_texts.append(text)
        total_chars += len(text)
    n_pages = len(doc)
    avg_chars_per_page = total_chars / n_pages if n_pages else 0
    full_text = "\n\n".join(page_texts)
    return full_text, avg_chars_per_page


def extract_with_ocr(pdf_path: Path) -> str:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = False

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    result = converter.convert(str(pdf_path))
    return result.document.export_to_markdown()


def convert_one(pdf_path: Path) -> tuple[bool, str, str]:
    """Returns (ok, method_used, error_message)."""
    out_path = output_path_for(pdf_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        text, avg_chars_per_page = extract_native_text(pdf_path)
        if avg_chars_per_page >= MIN_CHARS_PER_PAGE:
            out_path.write_text(text, encoding="utf-8")
            return True, "native", ""
    except Exception as exc:
        return False, "native", str(exc)

    try:
        text = extract_with_ocr(pdf_path)
        out_path.write_text(text, encoding="utf-8")
        return True, "ocr", ""
    except Exception as exc:
        return False, "ocr", str(exc)


def main() -> None:
    pdf_paths = find_pdfs(RAW_PDFS_DIR)
    if not pdf_paths:
        print(f"No PDFs found under {RAW_PDFS_DIR}")
        return

    to_process = []
    for pdf_path in pdf_paths:
        out_path = output_path_for(pdf_path)
        if out_path.exists() and out_path.stat().st_mtime >= pdf_path.stat().st_mtime:
            continue
        to_process.append(pdf_path)

    already_done = len(pdf_paths) - len(to_process)
    if already_done:
        print(f"Skipping {already_done} file(s) already converted.")

    if not to_process:
        print("Nothing new to convert.")
        return

    print(f"Converting {len(to_process)} file(s)...\n")

    successes = []
    failures = []

    for i, pdf_path in enumerate(to_process, start=1):
        rel = pdf_path.relative_to(RAW_PDFS_DIR)
        print(f"[{i}/{len(to_process)}] {rel} ...", end=" ", flush=True)
        start = time.time()
        ok, method, error_message = convert_one(pdf_path)
        elapsed = time.time() - start

        if ok:
            print(f"done via {method} ({elapsed:.1f}s)")
            successes.append(rel)
        else:
            print(f"FAILED during {method} ({elapsed:.1f}s)")
            failures.append((rel, error_message))

    print("\n--- Summary ---")
    print(f"Converted: {len(successes)}")
    print(f"Failed:    {len(failures)}")

    if failures:
        print("\nFiles that failed:")
        for rel, error_message in failures:
            print(f"  - {rel}")
            print(f"    {error_message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
