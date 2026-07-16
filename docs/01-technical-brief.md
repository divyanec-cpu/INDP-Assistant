# Technical Brief — defence-kb

Status as of 2026-07-07. This is the engineering constitution for this project: when in
doubt about architecture, data model, or build order, this document governs — everything
except a direct instruction from the founder (the user) in the moment.

## What this project is

A document question-answering system over Indian defence procurement regulations:

- **DPM 2009 / DPM 2025** — revenue procurement (in force from 1 Nov 2025; DPM 2009 still
  governs RFPs issued up to 31 Oct 2025).
- **DAP 2020** — capital acquisition, currently in force.
- **Draft DAP 2026** — released 11 Feb 2026 for public comment, NOT in force, must never be
  presented as current law.

The system answers plain-English questions and must cite every claim to a specific
`[doc_name, chapter, para]`, name the governing regime up front, and never blend revenue and
capital procedures. The full behavioral contract lives in
[03-design-spec.md](03-design-spec.md) and is mirrored into `CLAUDE.md` at the project root
because it is non-negotiable.

## Non-goals for this milestone

- No mobile app (Android or iOS) — explicitly deferred; see project memory. Phone access is
  instead a password-gated web page (Feature Pack F7 - see below), not an installable app.
- No multi-user accounts (a single shared password gates the whole page, not per-user logins).

## Environment

- Windows PC, user is a complete beginner at coding — explanations must stay in plain English.
- Project root: `C:\1 PROJECTS\defence-kb` (moved off OneDrive; OneDrive's file-locking broke
  `pip install` twice before the move — do not move the project back under OneDrive/Dropbox/etc.
  without expecting the same problem).
- Python 3.13.12, virtual environment at `.venv/`. The user never activates it manually — every
  command runs through `.venv\Scripts\python.exe` directly.
- Dependencies pinned in `requirements.txt` (generated via `pip freeze` after installing):
  `llama-index`, `llama-index-vector-stores-chroma`, `chromadb`, `docling`,
  `llama-index-embeddings-voyageai`, `voyageai`, `llama-index-llms-anthropic`, `anthropic`,
  `llama-index-retrievers-bm25`, `rank-bm25`, `python-dotenv`, `pandas`. Re-verify with an
  all-imports smoke check (see Regression Impact Pack) after any dependency change.

## Folder layout

```
raw_pdfs/          Source PDFs. READ-ONLY — never modified, moved, or deleted by any script.
processed_text/    Markdown mirror of raw_pdfs/, one .md per PDF, same subfolder structure.
config/
  .env             API keys (VOYAGE_API_KEY, ANTHROPIC_API_KEY). Gitignored, never printed.
  document_manifest.csv   Hand-maintained metadata, one row per source PDF (see Data model).
chunked/           Generated chunks with citation metadata (chunks.jsonl). Tracked in git
                   (needed by the deployed app), rebuildable from processed_text/ + the
                   manifest via chunk_documents.py.
chroma_store/      Chroma vector database (generated, tracked in git for deployment,
                   rebuildable from scratch via build_vector_index.py).
scripts/
  templates/       Jinja2 templates for the Flask web page (index.html).
eval/              Test questions + expected regime/citations, and the script that runs them.
docs/              This document set.
Procfile           Tells Render how to start the app in production (gunicorn).
```

`raw_pdfs/` and `processed_text/` are gitignored (not needed by the running app, only by the
one-time ingestion pipeline) — see Deployment below for what is and isn't tracked, and why.

## Architecture (pipeline)

1. ✅ **Ingestion** — `scripts/convert_pdfs.py` walks `raw_pdfs/` recursively, converts each PDF
   to text (native text-layer extraction via pypdfium2, OCR fallback only for genuinely scanned
   files), writes to `processed_text/` mirroring the folder structure.
2. ✅ **Manifest** — `config/document_manifest.csv` is the ground truth for which regime/version
   each file belongs to, hand-maintained.
3. ✅ **Chunking** — `scripts/chunk_documents.py` reads `processed_text/` + the manifest, splits
   each document into chunks tagged with metadata (`doc_name`, `status`, `effective_date`,
   `type`, `parent_doc`, `regime`, `chapter`, `para`) into `chunked/chunks.jsonl`.
4. ✅ **Embedding + indexing** — `scripts/build_vector_index.py` embeds each chunk via VoyageAI
   (`voyage-law-2`) and stores vectors + metadata in Chroma at `chroma_store/`.
5. ✅ **Hybrid retrieval** — `scripts/hybrid_retrieve.py` fuses Chroma vector search with a BM25
   keyword retriever (reciprocal rank fusion).
6. ✅ **Answer synthesis** — `scripts/ask.py` (`answer_question()`) calls Claude with the Design
   Spec's answer contract as the system prompt, strictly from retrieved chunks.
7. ✅ **Evaluation** — `scripts/run_eval.py` runs `eval/questions.json` against the real pipeline,
   checking mechanical pass/fail signals per Design Spec rule.
8. ✅ **Interface** — two ways to ask questions: `scripts/ask.py`'s command-line loop (local use),
   and `scripts/webapp.py` (a password-gated Flask page, deployed to Render for phone/laptop
   access from any network — see Deployment below and `docs/05-deployment-guide.md`).

## Deployment

Feature Pack F7 was originally scoped as "a local web page reachable over the same Wi-Fi" but
was revised once the core pipeline was working and the user wanted it reachable by other people
on *different* networks - that needs real internet-facing hosting, not just binding to
`0.0.0.0` on the home network.

- **Hosting:** Render (free tier), chosen over a quick tunnel (e.g. Cloudflare Tunnel) for a
  stable, permanent URL that works even when the local PC is off. Tradeoff: needs the project in
  git, pushed to GitHub, and the user creating accounts on both services themselves - account
  creation and payment/signup details are things Claude cannot do on the user's behalf.
- **What's tracked in git vs. not:** the deployed app needs `chroma_store/` (embedded vectors)
  and `chunked/chunks.jsonl` (BM25 rebuilds from this at runtime) - both tracked despite being
  "generated" artifacts, since re-embedding on every deploy would be slow and wasteful.
  `raw_pdfs/` and `processed_text/` are only needed for the one-time ingestion pipeline, not the
  running app, so both are gitignored to keep the repo lean.
- **Production server:** `gunicorn` (via `Procfile`), not Flask's own dev server - `gunicorn`
  does not run on Windows (relies on `os.fork`), so it's pinned in `requirements.txt` without
  local verification; it only actually gets exercised on Render's Linux build.
- **Access control:** a single shared password (`SHARED_ACCESS_PASSWORD` env var) via HTTP Basic
  Auth, compared with `secrets.compare_digest` (timing-safe). Chosen because every question spends
  real Voyage/Anthropic API credits once other people can reach the page - unrestricted public
  access would mean unrestricted spending.
- **Design:** `scripts/templates/index.html` is styled after a mockup the user shared via
  claude.ai's Design tool (project "Defence Procurement Query Interface"), simplified to fit a
  server-rendered, no-JavaScript page (full-page reload on submit) rather than the mockup's
  React-based client state. Regime badges are derived dynamically from whichever `doc_name`s are
  actually cited in a given answer (color-coded: green=DPM 2025, amber=DPM 2009, blue=DAP 2020,
  red=Draft DAP 2026 with an explicit not-in-force warning), not hardcoded to one badge per
  answer, since real answers can cite multiple regimes at once (Rule 8 version comparisons).
- Full step-by-step instructions for the parts only the user can do (GitHub/Render account
  creation, environment variable setup, the actual push and deploy) are in
  `docs/05-deployment-guide.md`.

## Data model

`config/document_manifest.csv` columns:

| Column | Meaning |
|---|---|
| `filename` | Relative path under `raw_pdfs/` |
| `doc_name` | Canonical name used in citations, e.g. "DPM 2025 Vol I" |
| `status` | `in-force` / `superseded` / `draft` |
| `effective_date` | ISO date the document took effect |
| `type` | `main` or `amendment` |
| `parent_doc` | For amendments, the `doc_name` of the main document it amends |
| `regime` | `revenue` or `capital` |
| `include_in_index` | `yes` / `no` — `no` for near-duplicate copies that would otherwise create redundant/conflicting citations (see `notes` for which ones and why) |
| `notes` | Freeform — anything a future session needs to know about this file |

These same fields (minus `filename`/`include_in_index`, plus `chapter`/`para`) become the
metadata attached to every chunk in the vector index, so citations can be generated and regime
rules enforced automatically at answer time.

Each record in `chunked/chunks.jsonl` (one per chunk) has: `doc_name`, `status`,
`effective_date`, `type`, `parent_doc`, `regime` (copied from the manifest row), `chapter`,
`para` (detected from the chunk's text — see build-order step 4), `source_file`, `chunk_index`,
`text`.

## Build order

1. ✅ Environment setup (Python, venv, packages, folders, `.env`, manifest template).
2. ✅ **PDF → text conversion — fixed.** Root cause: this machine has only 7.9 GB RAM (often
   well under 1 GB free), and Docling's default pipeline loads several AI vision models and
   rasterizes every page as an image for layout/OCR analysis. On long documents this exhausted
   memory partway through, and every subsequent page's "preprocess" stage failed with
   `std::bad_alloc` — silently, without raising an exception the script caught (exit code
   stayed 0). Confirmed on `DPM-2025-VOLUME-I.pdf`: expected several hundred KB of text, got
   ~17KB of scattered fragments. Disabling OCR alone did not fix it, because the crash was in
   page rasterization for layout analysis, not OCR specifically.

   Fix: `scripts/convert_pdfs.py` now extracts text directly from each PDF's native text layer
   via `pypdfium2` as the primary method — no AI models, minimal memory, and it turned out all
   20 source PDFs have a real text layer (checked chars/page for each; none were actually
   scanned despite a scan-sounding filename like `Iscan0005new.pdf`). Docling's OCR pipeline is
   kept only as an automatic fallback, triggered when a file's average characters-per-page falls
   below `MIN_CHARS_PER_PAGE` (200) — i.e. only for genuinely scanned PDFs, which none of the
   current files are. Re-run on all 20 files: 20/20 converted via the native path in ~15 seconds
   total, with byte sizes now proportional to page count (e.g. `DPM-2025-VOLUME-I.md` went from
   14.8 KB to 692 KB; `DAP2020.md` from 32.6 KB to 1.44 MB). Content spot-checked for
   completeness (runs to the correct final chapter/page) and legibility.

   **Known minor artifact:** a handful of PDFs have bilingual (Hindi/English) header lines set
   in a legacy non-Unicode Hindi font; those specific lines extract as garbled Latin characters
   (e.g. "j{kk ea=h" instead of "रक्षा मंत्री"). This does not affect the substantive English
   procurement text, only a few decorative header lines. Not fixed — noted as a known limitation.
3. ✅ Filled in `document_manifest.csv` for all 20 source files. Surfaced several findings
   recorded in the manifest's own `notes` column: `DPM_2025/DPM0001.pdf` is misfiled (it's
   actually a 2015 amendment to DPM 2009, not DPM 2025 — and we don't have DPM 2009's main text
   at all, only this one amendment); three DAP 2020 files are near-duplicate copies of the same
   pre-amendment text (now flagged `include_in_index = no`, see Data model); a few amendment
   dates have an illegible exact day in the OCR'd scan (month/year is solid).
4. ✅ **Chunking with chapter/para-aware splitting — done.** `scripts/chunk_documents.py` groups
   consecutive whole paragraphs into ~1,500-character chunks (splitting a single paragraph
   further only if it alone exceeds that size), tracking two regexes while scanning: a chapter
   heading (`CHAPTER 1` / `CHAPTER I` styles) and a paragraph number (`1.1.1 ...` / `5. ...`
   styles). Produced 4,537 chunks across the 17 included files to `chunked/chunks.jsonl`; only
   20 chunks (0.4%) got neither tag. Spot-checked 10 random chunks: 9/10 plausible, the 10th fell
   in a source PDF (`amendment_2011-11.pdf.pdf`) with ~8% corrupted/garbled characters baked into
   its original text layer — a pre-existing source-data quality issue, not an extraction bug.
   Known rough edges: a Table of Contents briefly causes incorrect chapter-cycling before real
   chapter content begins; dense tabular documents (e.g. DFPDS 2026) can bundle several numbered
   items into one chunk tagged with only the first item's number. See `docs/02-feature-pack.md`
   F3 for the full write-up.
5. ✅ **Embedding + indexing into Chroma — done.** `scripts/build_vector_index.py` embeds every
   chunk with VoyageAI's `voyage-law-2` model (chosen for this being entirely legal/regulatory
   text — checked current Voyage model lineup via web search rather than trust stale training
   data) and stores vectors + metadata in a persistent Chroma collection (`defence_kb`) at
   `chroma_store/`. All 4,537 chunks embedded successfully across two runs.

   The account had no payment method on file, which throttles Voyage requests to 3 RPM / 10K
   TPM - worse in practice than documented, since even correctly-paced requests were rejected
   consistently until a card was added (free tokens still apply regardless of payment method;
   this corpus is small enough that the run cost nothing either way). The script paces requests
   and retries on rate-limit errors with exponential backoff, and is idempotent - each chunk gets
   a stable id (`sha1(source_file::chunk_index)`), so a re-run only embeds what's missing rather
   than re-paying to re-embed everything. This is how the 25 chunks that failed during the
   pre-payment-method throttling got picked up cleanly on a second run.

   Smoke-tested with the query "weapons platforms banned for import" (a phrase drawn from real
   corpus content): top 3 results were the exact source amendment introducing that ban (DAP 2020
   BPR Phase II) plus two topically adjacent chapters of the consolidated DAP 2020 text - a
   strong sign retrieval is wired correctly end to end.
6. ✅ **Hybrid retrieval (vector + BM25) wiring — done.** `scripts/hybrid_retrieve.py` combines
   the existing Chroma vector retriever with a `BM25Retriever` (rebuilt in-memory from
   `chunked/chunks.jsonl` each run - the corpus is small enough that this is fast and avoids a
   second on-disk artifact that could drift out of sync with the chunks file), merged via
   `QueryFusionRetriever` in reciprocal-rank-fusion mode (combines by rank position, not raw
   score, since BM25 and cosine-similarity scores aren't on comparable scales). Query expansion
   is disabled (`num_queries=1`) so retrieval doesn't require an LLM call - though
   `QueryFusionRetriever`'s constructor unconditionally resolves an LLM regardless (it defaults
   to OpenAI via a global lookup, which errored since this project has no OpenAI key); fixed by
   passing our actual LLM (Anthropic) explicitly instead.

   Verified with 4 hand-picked queries spanning semantic and keyword-heavy phrasing (not the
   full F6 eval harness, just enough to confirm the fusion before building on it): a keyword
   query for "60 days after warranty period" surfaced near-exact phrase matches ("60 days beyond
   the period of warranty") from DPM 2025, a rupee-amount query surfaced genuine ₹/crore figures
   across multiple documents, and the known-good "weapons platforms banned for import" query
   (used in the embedding step's smoke test) returned consistent results. Also fixed a Windows
   console encoding crash when printing the ₹ character (stdout reconfigured to UTF-8).
7. ✅ **Answer synthesis with Claude — done.** `scripts/ask.py` retrieves via
   `hybrid_retrieve.build_hybrid_retriever()`, formats the top 10 chunks (all metadata fields
   plus text) into context, and calls Claude (`claude-sonnet-5`, `temperature=0.1`,
   `max_tokens=2048` - the Anthropic wrapper's default of 512 was too small for a detailed
   multi-citation answer) via `llama_index.llms.anthropic.Anthropic`. The system prompt is the
   Design Spec's answer contract (rules 1-8) reproduced verbatim as a Python string constant -
   a hand-maintained mirror, same discipline as `CLAUDE.md` itself; if the Design Spec's rules
   ever change, this constant needs updating too.

   Note on the LLM call itself: `Anthropic.complete()` does *not* accept a `system_prompt` kwarg
   per-call (checked the source directly rather than assume) - the system prompt has to be an
   actual `ChatMessage(role=MessageRole.SYSTEM, ...)` passed to `.chat()`, which is what the
   script does.

   Tested with 5 real questions spanning all four regimes plus an out-of-scope question. All
   five followed the answer contract correctly: regime named first every time; the DPM cutover
   rule was applied correctly and unprompted, with the actual savings-clause paragraph cited
   (DPM 2025 Vol I, Para 1.1.3); draft DAP 2026 was correctly flagged as not-in-force with the
   exact dates (11 Feb 2026 release, 3 Mar 2026 comment deadline); an amendment-vs-main-text
   reconciliation was demonstrated unprompted (DAP 2020 BPR Phase II amendment vs. the
   consolidated text); and the out-of-scope pension question got the exact required refusal
   phrase ("The provided documents do not contain this") rather than an invented answer. A light
   automated sanity check flags any answer over ~200 characters with no `[doc_name, chapter,
   para]`-style citation - refined after the first test run to not fire on legitimate Rule 7
   refusals (which correctly have no citations).

   Per `CLAUDE.md`'s verification split: the above is what I can check mechanically (rules were
   visibly followed, citations were present and correctly formatted). Whether every individual
   citation's content is actually *accurate* against the real regulation requires the user's own
   domain knowledge to fully confirm - worth a skim before relying on this for anything real.
8. ✅ **Evaluation harness — done.** `eval/questions.json` has 10 written test cases covering
   every F5 criterion (a)-(g) plus a keyword-retrieval regression check, each with mechanical
   pass/fail signals (expected/forbidden regime mentions, citation-presence, required phrases,
   Rule 5/7-specific phrase checks). `scripts/run_eval.py` runs the real pipeline
   (`ask.answer_question()` - the same function the interactive CLI uses, so eval exercises the
   actual code path, not a separate mock) against all 10 and reports pass/fail per check, exiting
   non-zero on any failure so it can serve as a release gate per the Regression Impact Pack.

   First run: 25/25 checks passed across all 10 questions. Spot-checked the two riskiest answers
   by eye rather than trust the mechanical pass alone (per the verification split - these checks
   confirm a rule's *signal* is present, not that its content is accurate): the thin-DPM-2009
   question correctly answered from the one amendment available and explicitly noted the
   original pre-amendment paragraph text isn't in the corpus, rather than inventing it; the
   deliberately ambiguous "acquisition categories" question correctly reasoned that the term is
   specifically a capital-acquisition concept and explicitly excluded DPM rather than blending
   revenue and capital content, while clearly labeling a DPP 2016 mention as a separate
   "superseded" historical note.

   Known gap: rule (g) version-comparison phrasing wasn't separately isolated as its own pass/
   fail check beyond "both regime names mentioned" - the two-sided contrast quality itself was
   only confirmed by eye, not mechanically. Worth a sharper check if this harness grows.
9. ✅ **Phone/laptop access from any network — done.** See the Deployment section above and
   `docs/05-deployment-guide.md`. Revised from the original "same Wi-Fi" scope once the user
   wanted it reachable by other people on different networks: cloud-hosted on Render with a
   password gate, rather than a local-network-only page.

## Known risks / issues log

- **OCR crash / silent data loss** (see build order step 2) — resolved.
- **Chapter-tracking imprecision in Table-of-Contents sections and dense tabular documents**
  (see build order step 4) — known limitation, not fixed.
- **Corrupted source text layer in `amendment_2011-11.pdf.pdf`** (~8% of characters garbled) —
  a pre-existing quality issue in that source PDF itself, not something our pipeline introduced
  or can fix. Low practical impact expected: bad chunks just won't retrieve well for real
  queries, which fails safely into the Design Spec's "not in context" rule rather than
  surfacing wrong information.
- **OneDrive file locking** broke `pip install` twice — resolved by moving the project to
  `C:\1 PROJECTS\defence-kb`. Do not relocate back under a syncing folder.
- Several source filenames have doubled extensions (e.g. `amendment_2011-11.pdf.pdf`) — cosmetic,
  the conversion script handles it fine, but worth cleaning up in the manifest's `filename`
  column for readability.
