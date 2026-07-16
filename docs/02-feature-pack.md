# Feature Pack — defence-kb

Feature-by-feature scope for the current milestone (build the working pipeline end to end on
this PC). Each feature has a "Done when" line — that line is its acceptance test. If a feature
isn't listed here, it isn't in this milestone; do not add scope beyond what's written without
updating this document first.

## F1 — PDF ingestion

Convert every PDF in `raw_pdfs/` into clean Markdown text.

**Done when:** every PDF in `raw_pdfs/` has a corresponding `.md` file in `processed_text/`,
and each file's extracted character count is proportional to its source page count (spot-check:
roughly 1-3 KB of text per page for dense policy documents — a 295-page document producing 17KB
is a fail, not a pass, even if the script's own exit code is 0). No file may be silently
truncated or empty without the run being flagged.

**Status:** done — see Technical Brief build-order step 2 for the fix (switched to native
text-layer extraction via pypdfium2; OCR kept as an automatic fallback for genuinely scanned
files, none of which exist in the current 20). All 20 files converted, byte sizes now
proportional to page count, spot-checked for completeness.

## F2 — Document manifest

One correctly filled row per source PDF in `config/document_manifest.csv`.

**Done when:** all 20 rows are present with correct `doc_name`, `status` (in-force /
superseded / draft), `effective_date`, `type` (main / amendment), `parent_doc` (set for every
amendment row, pointing to its main document's `doc_name`), and `regime` (revenue / capital).
Draft DAP 2026 must be marked `status = draft`. DPM 2009 vs DPM 2025 status must reflect the
1 Nov 2025 cutover correctly for any file that represents either version.

**Status:** done — all 20 rows filled in and CSV-validated. Several findings surfaced while
filling it in, all recorded in the manifest's own `notes` column and worth the user's attention:

- `DPM_2025/DPM0001.pdf` is misfiled — it's actually a 2015 amendment to the older **DPM 2009**,
  not DPM 2025. We don't have DPM 2009's main text at all, only this one amendment to it.
- Three files (`DAP2020.pdf`, `DAP_2020 _main.pdf`, `DAP2030new_0.pdf`) are near-duplicate copies
  of the same pre-amendment DAP 2020 text; marked `status = superseded` with a recommendation to
  exclude them from indexing in favor of `DAP-2020_after_BPR_Ph_V_01_APR_2024.pdf`, which is the
  consolidated, current text (incorporates all 5 "BPR phase" amendments, Nov 2021 - Apr 2024).
- A few amendment dates have an exact day that's illegible in the OCR'd scan (flagged per-row);
  the month/year is solid but worth the user double-checking the source PDF if day-level
  precision ever matters for a specific question.
- Two files are draft/unsigned internal documents, not notified policy (the DAP 2026 draft, and
  a separately-drafted, undated "simulation-based trials" guidance letter).

## F3 — Metadata-aware chunking

Split each document into retrieval-sized chunks that carry full citation metadata.

**Done when:** every chunk stored in the vector index carries `doc_name`, `status`,
`effective_date`, `type`, `parent_doc`, `regime`, `chapter`, and `para`. A manual spot-check of
10 random chunks shows the chapter/para values actually match the chunk's content (not off-by-one
or defaulted to blank).

**Status:** done — `scripts/chunk_documents.py` produced 4,537 chunks across the 17 included
files (see `include_in_index` column, added to the manifest) to `chunked/chunks.jsonl`, with
only 20 chunks (0.4%) getting neither a chapter nor a para tag. Spot-check of 10 random chunks:
9/10 had chapter/para values plausibly consistent with their content; the 10th landed in a
region of `amendment_2011-11.pdf.pdf` with corrupted source text (~8% of that file's characters
are garbled/invalid Unicode - a pre-existing quality issue in that specific source PDF's text
layer, not something introduced by our extraction). Known rough edges, not fixed this round:
Table-of-Contents sections briefly cause incorrect chapter-cycling before real chapter content
begins; dense tabular documents (e.g. DFPDS 2026) can bundle multiple numbered items into one
chunk, tagged with only the first item's number. Per `CLAUDE.md`'s verification split, this
spot-check is something I can partially verify myself (structure, plausibility) but real
correctness for domain-specific numbering conventions is worth the user's own glance too.

## F4 — Hybrid retrieval

Combine vector similarity search (Chroma) with keyword search (BM25).

**Done when:** for a shortlist of ~10 known test questions (see `eval/`), the merged retrieval
result includes the chunk(s) known to contain the correct answer, for both a well-worded query
and a keyword-heavy query (e.g. a specific rupee threshold or paragraph number).

**Status:** done — `scripts/hybrid_retrieve.py` fuses the Chroma vector retriever with a BM25
keyword retriever via reciprocal rank fusion. Verified with 4 hand-picked queries (not yet the
full ~10-question `eval/` set from F6 - that's a separate, later feature): a keyword-heavy query
("60 days after warranty period") returned near-exact phrase matches; a rupee-amount query
surfaced genuine ₹/crore figures; a semantic query ("delivery schedule timeframe") returned
topically relevant provisions including a literal "Delivery Schedule" paragraph; and the
known-good "weapons platforms banned for import" query stayed consistent with the embedding
step's earlier smoke test. Full technical detail (fusion mode choice, the LLM-resolution quirk
in `QueryFusionRetriever`'s constructor, an unrelated Windows console encoding fix) is in
`docs/01-technical-brief.md` build-order step 6.

## F5 — Regime-aware answer synthesis

Claude answers strictly from retrieved chunks, following the fixed behavioral contract (full
text in [03-design-spec.md](03-design-spec.md), mirrored in `CLAUDE.md`).

**Done when**, across a batch of test questions spanning all four regimes (DPM 2009, DPM 2025,
DAP 2020, draft DAP 2026):
- (a) every answer names the governing regime before anything else;
- (b) every factual claim carries a `[doc_name, chapter, para]` citation;
- (c) date/RFP-based questions apply the DPM cutover rule explicitly and correctly;
- (d) any citation of draft DAP 2026 is flagged as "draft, not in force";
- (e) where an amendment and main text conflict on the same para, the amendment's position is
  stated as governing, with both cited;
- (f) questions with no answer in the retrieved context get "The provided documents do not
  contain this" rather than an invented answer;
- (g) version-comparison questions get a point-by-point contrast with citations on both sides.

**Status:** done — `scripts/ask.py`. Tested with 5 real questions (not the full F6 batch, which
is a separate next feature): a plain DPM 2025 question, a pre-cutover-RFP question, a DAP 2020
capital question, a draft-DAP-2026 question, and an out-of-scope question. All 5 criteria above
were demonstrated: regime named first every time (a); citations present and correctly formatted
throughout (b); the cutover rule applied correctly and unprompted, citing the actual
savings-clause paragraph (c); draft DAP 2026 flagged as not-in-force with exact dates (d); an
amendment-vs-main-text reconciliation demonstrated unprompted (e); the out-of-scope question got
the exact required refusal phrase (f). Version-comparison phrasing (g) wasn't specifically
tested this round - worth including in the F6 batch. Full detail in
`docs/01-technical-brief.md` build-order step 7, including a fix for the citation-detection
sanity check false-triggering on legitimate Rule 7 refusals.

## F6 — Evaluation harness

A repeatable check that the system still obeys its own rules after any change.

**Done when:** `eval/` contains a written set of test questions with their expected regime and
expected citation(s), and a script exists that runs the full pipeline against each question and
reports a pass/fail per rule from F5 (not just "an answer was produced").

**Status:** done — `eval/questions.json` (10 cases covering F5 criteria (a)-(g) plus a keyword
regression check) and `scripts/run_eval.py`. First run: 25/25 mechanical checks passed. Two
riskiest answers (thin-DPM-2009 corpus, the deliberately ambiguous "acquisition categories"
question) were also read by eye rather than trusting the mechanical pass alone - both held up
well. Full detail, including the one known gap (rule (g)'s two-sided contrast *quality* isn't
mechanically checked, only that both regime names appear), is in
`docs/01-technical-brief.md` build-order step 8.

## Out of scope for this milestone (explicitly deferred)

- **F7 — Phone/mobile access.** Not designed, not built. When revisited, default direction is a
  local web page reachable over Wi-Fi rather than an installable app (a true iOS app would
  additionally require a Mac + Xcode + Apple Developer account, which isn't available here).
- Any GUI beyond a plain command-line loop.
- Multi-user support, authentication, or cloud hosting.
