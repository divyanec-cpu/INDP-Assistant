# Regression Impact Pack — defence-kb

What to retest after each type of change. This runs alongside every other document — it is
never overridden.

## Retest matrix, by change type

| Change made | Retest |
|---|---|
| Edited `scripts/convert_pdfs.py` or upgraded Docling | Re-run conversion on all 20 PDFs. Compare output byte-size per file against the previous run — flag any file that shrank. Spot-check 3 files (one large main document, one amendment, one known-scanned file) by reading the actual Markdown, not just checking the exit code. |
| Edited chunking logic | Re-run indexing end to end. Check total chunk count is in a sane range (not near-zero, not wildly higher). Spot-check 10 random chunks' `chapter`/`para` metadata against the source text. |
| Edited `config/document_manifest.csv` | Re-run indexing (metadata is joined from the manifest at index time). Confirm citations changed only for the rows actually edited — nothing else should move. |
| Edited answer-synthesis prompt/rules | Re-run the full `eval/` question set. Every rule in the Design Spec's answer contract must still pass (citation format, regime-first, cutover rule, draft-2026 flagging, amendment precedence, "not in context" fallback, version-comparison format) — not just "an answer came back." |
| Any dependency/package version change | Re-run the all-imports smoke check. Then re-run one full conversion and one full end-to-end query. |
| Any change to `raw_pdfs/` (new PDF added) | Confirm the manifest has a new row for it before running conversion/indexing on it. Confirm no existing file in `raw_pdfs/` was modified, moved, or deleted as a side effect. |

## Smoke Suite (run before every release / milestone completion)

1. **Import check** — every pinned package in `requirements.txt` imports without error,
   including the specific `llama_index.vector_stores.chroma`, `llama_index.embeddings.voyageai`,
   `llama_index.llms.anthropic`, and `llama_index.retrievers.bm25` submodules actually used.
2. **Convert one sample PDF** end to end and confirm the output is non-trivial and legible.
3. **Ask one known question from each of the four regimes** (DPM 2025 revenue, DPM 2009
   revenue/cutover, DAP 2020 capital, draft DAP 2026) and confirm: correct regime named first,
   correct citation format, cutover rule applied where relevant, draft flagging applied where
   relevant.
4. **Confirm `raw_pdfs/` is untouched** — no script has modified, moved, or deleted anything in
   it.

## Release gates, by release type

- **Data-only change** (new PDF added, manifest row edited, no code changed): run the
  conversion/indexing retest rows above for the affected file(s). Full Smoke Suite not required
  unless the change affects `regime` or `status` for an existing in-force document.
- **Logic change** (chunking, retrieval, or answer-synthesis prompt/rules): full Smoke Suite +
  the complete `eval/` question set. Do not ship on a partial eval run.
- **Environment change** (new package version, Python upgrade, moved project folder): all-imports
  smoke check + full Smoke Suite. This is exactly the class of change that broke the pipeline
  silently before (the OCR crash was only caught because output size was checked, not just exit
  code) — never skip this gate for environment changes.
