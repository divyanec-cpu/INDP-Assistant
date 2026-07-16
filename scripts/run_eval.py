"""
Runs the fixed question set in eval/questions.json against the real answer
pipeline (scripts/ask.py) and checks each answer against a set of mechanical
heuristics derived from the Design Spec's answer contract - e.g. "does the
expected regime name appear", "is a [doc_name, chapter, para]-style citation
present", "does the required phrase appear".

These checks are a proxy for "the rule was visibly followed," not a
substitute for a human confirming a citation's content is actually accurate -
see docs/01-technical-brief.md and CLAUDE.md's verification split.

Run it from the project root with:
    .venv\\Scripts\\python.exe scripts\\run_eval.py

Exits non-zero if any check fails, so this can be used as a release gate.
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ask import answer_question, build_llm, CITATION_PATTERN
from hybrid_retrieve import build_hybrid_retriever

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = PROJECT_ROOT / "eval" / "questions.json"


def check_question(question: dict, answer: str) -> list[tuple[str, bool]]:
    """Returns a list of (check_description, passed) tuples."""
    checks = []
    answer_lower = answer.lower()

    for regime in question.get("expected_regime_mentions", []):
        checks.append((f"mentions '{regime}'", regime.lower() in answer_lower))

    for regime in question.get("forbidden_regime_mentions", []):
        checks.append((f"does NOT assert '{regime}' as governing", regime.lower() not in answer_lower))

    if question.get("must_contain_citation"):
        checks.append(("contains a [doc_name, chapter, para]-style citation", bool(CITATION_PATTERN.search(answer))))

    if question.get("must_flag_draft_not_in_force"):
        checks.append(("flags 'draft'", "draft" in answer_lower))
        checks.append(("flags 'not in force'", "not in force" in answer_lower))

    if question.get("must_be_rule7_refusal"):
        checks.append(("gives the Rule 7 refusal phrase", "do not contain this" in answer_lower))

    for phrase in question.get("required_phrases", []):
        checks.append((f"contains phrase '{phrase}'", phrase.lower() in answer_lower))

    return checks


def main() -> None:
    with QUESTIONS_PATH.open(encoding="utf-8") as f:
        questions = json.load(f)

    print("Building retriever and LLM...")
    retriever = build_hybrid_retriever()
    llm = build_llm()
    print(f"Running {len(questions)} eval question(s)...\n")

    total_checks = 0
    total_passed = 0
    any_question_failed = False

    for question in questions:
        print(f"=== {question['id']} ===")
        print(f"Q: {question['question']}")
        answer = answer_question(question["question"], retriever, llm)
        checks = check_question(question, answer)

        question_passed = True
        for description, passed in checks:
            total_checks += 1
            total_passed += passed
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {description}")
            if not passed:
                question_passed = False

        if not question_passed:
            any_question_failed = True
            print("  --- answer (for review) ---")
            print("  " + answer.replace("\n", "\n  "))

        print()

    print("--- Summary ---")
    print(f"Checks passed: {total_passed}/{total_checks}")
    print(f"Questions with at least one failed check: "
          f"{'yes' if any_question_failed else 'none'}")

    if any_question_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
