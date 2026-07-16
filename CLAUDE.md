# CLAUDE.md — Standing Rules for defence-kb

Read this first, every session. These rules bind every session and override convenience —
everything except a direct instruction from the founder (the user) in the moment. Full detail
lives in `docs/`; this file is the condensed, non-negotiable version.

## Who this project is for

The user is a complete beginner at coding, on Windows, using Claude Code's desktop app.
Explanations must stay in plain English — never assume familiarity with terminals, virtual
environments, package managers, or git. Explain what a step does before or while doing it.

## Privacy and data rules

- `raw_pdfs/` is **read-only**. Never modify, move, rename, or delete anything inside it,
  under any circumstance, without the user explicitly asking for that specific action.
- `config/.env` holds API keys. Never print its contents to chat, logs, or commit messages.
  It is gitignored — keep it that way.
- Nothing in this project gets pushed to a remote/shared location without the user explicitly
  asking for that specific push.

## Working method rules

- Pin dependency versions in `requirements.txt`; after any dependency change, re-run the
  all-imports smoke check before declaring it done (see `docs/04-regression-impact-pack.md`).
- **Never trust a script's exit code alone.** A conversion or processing script can exit 0
  while silently losing most of its data (this happened: Docling's OCR pipeline crashed
  per-page with `std::bad_alloc` on large PDFs, exit code stayed 0, and ~95% of a 295-page
  document's text was missing). Always sanity-check output size/content against a rough
  expectation, not just "did it crash."
- Confirm before large architecture-level pivots (e.g., building a mobile app) rather than
  scoping and building — the user needs to weigh in on scope decisions like that.
- Do not add features, scope, or interfaces beyond what `docs/02-feature-pack.md` lists for the
  current milestone. If it's not written there, it's not in scope yet — raise it as a question
  or a doc update, don't just build it.
- This project previously lived under OneDrive and broke `pip install` twice due to file
  locking. It now lives at `C:\1 PROJECTS\defence-kb`. Do not move it back under a
  syncing/cloud-drive folder without expecting the same failure mode.

## Domain rules (the actual product — non-negotiable)

Every answer this system ever produces must follow this contract in full (mirrored in
`docs/03-design-spec.md`, which has the complete explanation and examples):

1. Cite every claim as `[doc_name, chapter, para]`. No claim without a citation.
2. State the governing regime first — DPM 2025, DPM 2009, DAP 2020, or draft DAP 2026.
3. Never mix revenue (DPM) and capital (DAP) procedures in one answer.
4. Apply the DPM cutover rule explicitly: DPM 2025 governs RFPs issued on/after 1 Nov 2025
   (and any retracted-then-reissued RFP); DPM 2009 (amended) governs RFPs issued up to
   31 Oct 2025.
5. Draft DAP 2026 is NOT in force — flag it as draft whenever cited; DAP 2020 remains
   operative.
6. Where an amendment and main text conflict on the same paragraph, the amendment prevails —
   state both positions, cite both.
7. If the answer isn't in the provided context, say so plainly. No outside knowledge, no
   invented paragraph numbers.
8. Version-comparison questions get a point-by-point contrast, each side cited.

## Verification split (what "done" means)

Per `docs/Project_Kickoff_Build_Discipline_Playbook.docx` §4: two different kinds of "done."

- **Claude can verify alone:** code runs without error, imports succeed, byte-size/sanity checks
  on converted files, retrieval returns the expected chunk for a known query, citation format is
  syntactically correct, automated `eval/` pass/fail.
- **Only the user can verify:** whether a generated answer is actually *correct* per their real
  domain knowledge, whether a manifest row's regime/status/date assignment is right, whether the
  system "feels" trustworthy enough to rely on for real procurement questions.

**Reporting rule:** for anything in the second category, report it as "applied — needs your
confirmation," never as "fixed" or "done." Treat one verification round per milestone as the
normal rhythm, not a failure.

**Plan-mode rule:** favor plan mode being on before any feature-sized unit of work (it forces
scope onto one page for approval before building — the cheapest point to catch a misread spec).
It's fine to skip for small, well-scoped fix-rounds where the direction is already clear.

## Relationship to other documents

- `docs/01-technical-brief.md` — architecture, data model, build order.
- `docs/02-feature-pack.md` — scope for the current milestone.
- `docs/03-design-spec.md` — the full answer contract and interaction model.
- `docs/04-regression-impact-pack.md` — what to retest after each change type.
- Claude's own persistent memory (outside this repo) holds process lessons and project facts
  that should carry across sessions automatically. It is a notebook, not law — anything that
  must be enforced belongs in this file instead, not just in memory.
