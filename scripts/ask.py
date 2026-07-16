"""
Answers questions about Indian defence procurement regulations, strictly from
retrieved chunks, following the answer contract in docs/03-design-spec.md
(cite every claim, name the governing regime first, never mix revenue/capital,
apply the DPM cutover rule, flag draft DAP 2026 as not in force, reconcile
amendments over main text, say plainly when the answer isn't in context).

Requires VOYAGE_API_KEY and ANTHROPIC_API_KEY in config/.env, and an
already-populated Chroma collection (see build_vector_index.py).

Run it from the project root with:
    .venv\\Scripts\\python.exe scripts\\ask.py
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.llms.anthropic import Anthropic

from hybrid_retrieve import build_hybrid_retriever

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Verbatim from docs/03-design-spec.md's "Answer contract" section. If that
# section is ever edited, this constant must be updated to match - it is a
# hand-maintained mirror, not auto-generated (same discipline as CLAUDE.md).
SYSTEM_PROMPT = """You are a precise assistant answering questions about Indian defence procurement regulations.
You answer ONLY from the provided context chunks. Each chunk includes metadata: doc_name,
status (in-force/superseded/draft), effective_date, type (main/amendment), parent_doc,
chapter, and para.

RULES:
1. CITE EVERY CLAIM. After each statement, cite the source in the form
   [doc_name, chapter, para]. Example: "The LD ceiling is 10% [DPM 2025 Vol I,
   Chapter X, Para Y]." Never state a fact without a citation from the context.

2. STATE THE GOVERNING REGIME. Begin the answer by naming which regulation governs:
   DPM 2025, DPM 2009, DAP 2020, or draft DAP 2026. If a question spans versions,
   answer for each version separately and state what changed.

3. REVENUE vs CAPITAL. DPM (2009/2025) governs REVENUE procurement; DAP
   (2020/draft 2026) governs CAPITAL acquisition. Do not mix them.

4. DPM CUTOVER RULE. DPM 2025 is in force from 1 November 2025. RFPs issued up to
   31 October 2025 remain governed by DPM 2009 (amended). RFPs issued on/after
   1 November 2025 - and retracted-then-reissued RFPs - are governed by DPM 2025.
   If the question involves a date or an existing RFP, apply this rule explicitly.

5. DRAFT DAP 2026 IS NOT IN FORCE. It was released as a DRAFT on 11 February 2026
   for public comment (comments due 3 March 2026) and has NOT been notified.
   Whenever you cite it, flag it as "draft, not in force" and note that DAP 2020
   remains the operative capital procedure. Never present a draft DAP 2026
   provision as current law.

6. RECONCILE AMENDMENTS. If the context contains an amendment chunk (type=amendment)
   whose para matches a main-text para, the amendment PREVAILS over the original for
   that paragraph. State the original position, then the amended position, and cite
   both. Example: "Para 12 originally required X [DAP 2020, Ch III, Para 12]; the
   September 2024 amendment revised this to Y [DAP 2020 Amendment Sep 2024, Para 12]."

7. IF THE ANSWER IS NOT IN THE CONTEXT, say so plainly: "The provided documents do
   not contain this." Do NOT use outside knowledge and do NOT invent paragraph numbers.

8. When comparing versions (e.g., DPM 2009 vs DPM 2025), present a short point-by-point
   contrast and cite each side."""

MODEL_NAME = "claude-sonnet-5"
SIMILARITY_TOP_K = 10
MAX_TOKENS = 2048
TEMPERATURE = 0.1

CITATION_PATTERN = re.compile(r"\[[^\[\]]+\]")


def format_context(nodes) -> str:
    blocks = []
    for i, node_with_score in enumerate(nodes, start=1):
        meta = node_with_score.node.metadata
        block = (
            f"[Chunk {i}]\n"
            f"doc_name: {meta.get('doc_name')}\n"
            f"status: {meta.get('status')}\n"
            f"effective_date: {meta.get('effective_date')}\n"
            f"type: {meta.get('type')}\n"
            f"parent_doc: {meta.get('parent_doc')}\n"
            f"regime: {meta.get('regime')}\n"
            f"chapter: {meta.get('chapter')}\n"
            f"para: {meta.get('para')}\n"
            f"text: {node_with_score.node.get_content()}"
        )
        blocks.append(block)
    return "\n\n".join(blocks)


def answer_question(question: str, retriever, llm) -> str:
    nodes = retriever.retrieve(question)
    context = format_context(nodes)

    user_message = f"Context chunks:\n\n{context}\n\nQuestion: {question}"

    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
        ChatMessage(role=MessageRole.USER, content=user_message),
    ]
    response = llm.chat(messages)
    answer = response.message.content or ""

    is_rule7_refusal = "do not contain this" in answer.lower()
    if len(answer) > 200 and not CITATION_PATTERN.search(answer) and not is_rule7_refusal:
        answer += (
            "\n\n[NOTE: no [doc_name, chapter, para] citation was detected anywhere in "
            "this answer, which Rule 1 requires for every claim - treat this answer with "
            "extra caution.]"
        )

    return answer


def build_llm() -> Anthropic:
    load_dotenv(PROJECT_ROOT / "config" / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set in config/.env")
    return Anthropic(
        model=MODEL_NAME,
        api_key=api_key,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )


def main() -> None:
    print("Building retriever and LLM...")
    retriever = build_hybrid_retriever(similarity_top_k=SIMILARITY_TOP_K)
    llm = build_llm()
    print("Ready. Type a question, or 'exit' to quit.\n")

    while True:
        question = input("> ").strip()
        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            break

        answer = answer_question(question, retriever, llm)
        print(f"\n{answer}\n")


if __name__ == "__main__":
    main()
