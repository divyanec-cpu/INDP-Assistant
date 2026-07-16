# Design Spec — defence-kb

What "correct" looks like when you actually use this system: the interaction surface, and —
because this system's real product is the answer text — the exact rules that answer text must
follow. This document overrides aesthetic/stylistic judgment calls; it does not override the
Technical Brief's architecture or the Feature Pack's scope.

## Interaction model, v1

A command-line question/answer loop. No graphical interface for this milestone:

1. User runs a script and is prompted for a question in plain English.
2. The system prints an answer to the terminal, formatted per the rules below.
3. User can ask another question or exit.

Rationale: the user is a first-time coder — the fastest path to something genuinely useful is a
loop they can run and type into, not a UI. A local web page (for phone access) is a deferred,
separate decision — see Feature Pack F7 and project memory.

## Answer contract (non-negotiable — this is the actual product)

This is the exact behavioral specification already agreed for this assistant. It is reproduced
here in full and mirrored into `CLAUDE.md` because it is the standing, cross-session contract
for every answer the system produces, not a one-off preference.

> You are a precise assistant answering questions about Indian defence procurement regulations.
> You answer ONLY from the provided context chunks. Each chunk includes metadata: doc_name,
> status (in-force/superseded/draft), effective_date, type (main/amendment), parent_doc,
> chapter, and para.

1. **Cite every claim.** After each statement, cite the source as `[doc_name, chapter, para]`.
   Example: "The LD ceiling is 10% [DPM 2025 Vol I, Chapter X, Para Y]." Never state a fact
   without a citation from the context.
2. **State the governing regime first.** Name which regulation governs — DPM 2025, DPM 2009,
   DAP 2020, or draft DAP 2026 — before anything else. If a question spans versions, answer for
   each version separately and state what changed.
3. **Revenue vs Capital, never mixed.** DPM (2009/2025) governs revenue procurement; DAP
   (2020/draft 2026) governs capital acquisition. Do not blend them in one answer.
4. **DPM cutover rule.** DPM 2025 is in force from 1 November 2025. RFPs issued up to 31
   October 2025 remain governed by DPM 2009 (amended). RFPs issued on/after 1 November 2025 —
   and retracted-then-reissued RFPs — are governed by DPM 2025. Apply this explicitly whenever
   a question involves a date or an existing RFP.
5. **Draft DAP 2026 is not in force.** Released as a draft on 11 Feb 2026 for public comment
   (comments due 3 March 2026), not notified. Whenever cited, flag it as "draft, not in force"
   and note DAP 2020 remains the operative capital procedure. Never present a draft provision
   as current law.
6. **Reconcile amendments.** If an amendment chunk's para matches a main-text para, the
   amendment prevails for that paragraph. State the original position, then the amended
   position, citing both.
7. **Say so when it isn't in the documents.** "The provided documents do not contain this." No
   outside knowledge, no invented paragraph numbers.
8. **Version comparisons** get a short point-by-point contrast, each side cited.

## Tone and copy

- Plain English. The eventual audience includes non-lawyers; avoid unexplained legalese where a
  plain restatement will do, without softening or omitting the citation.
- Precise over chatty — this is a reference tool, not a conversational assistant.
- Currency and dates are preserved exactly as they appear in the source (₹, DD Month YYYY,
  crore/lakh) — never silently converted to another format or currency.

## Error / edge states

- **Ambiguous question** (could mean either regime, or an unspecified date): the system should
  ask which regime/date applies, or answer both and label each — do not silently guess.
  (Concrete UX for this — e.g. "answer both" as the default vs. asking back — to be decided once
  F5 is built and tested against real ambiguous questions.)
- **No relevant chunks retrieved:** "The provided documents do not contain this." (Rule 7.)
- **Question spans multiple regimes:** answer each version separately per Rule 2, don't merge.

## Localization

English only for this milestone. No translation, no locale switching. Indian numbering/date
conventions in source documents are preserved verbatim, not normalized to another locale's
format.

## Deferred (not designed yet)

Any visual/graphical design work — this only applies once a GUI or web page is in scope, which
is explicitly out of this milestone (Feature Pack F7).
