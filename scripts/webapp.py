"""
Flask web page for the defence-kb Q&A pipeline - phone/laptop-accessible once
deployed (see docs/05-deployment-guide.md). Styled after a design mockup the
user shared via claude.ai's Design tool (project "Defence Procurement Query
Interface"), simplified to fit this app's server-rendered, no-JavaScript
architecture: full-page reload on submit, one answer per request, no client-
side state.

Gated with HTTP Basic Auth against a single shared password (SHARED_ACCESS_PASSWORD)
since real Voyage/Anthropic API costs are incurred per question once other
people can reach this. Browsers show their own native username/password
prompt for this - no custom login page or session/cookie code needed.

Requires VOYAGE_API_KEY, ANTHROPIC_API_KEY, and SHARED_ACCESS_PASSWORD in
config/.env for local testing, or as real environment variables once deployed.

Run it locally (Flask's own dev server - NOT gunicorn, which doesn't run on
Windows) from the project root with:
    .venv\\Scripts\\python.exe scripts\\webapp.py
Then open http://127.0.0.1:5000 in a browser.
"""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, render_template, request

from ask import CITATION_PATTERN, answer_question, build_llm
from hybrid_retrieve import build_hybrid_retriever

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / "config" / ".env")

SHARED_PASSWORD = os.environ.get("SHARED_ACCESS_PASSWORD")
if not SHARED_PASSWORD:
    raise SystemExit(
        "SHARED_ACCESS_PASSWORD not set - add it to config/.env for local testing, "
        "or as an environment variable on the hosting platform."
    )

REGIME_STYLES = {
    "DPM 2025": {"bg": "#123A24", "fg": "#7FD6A4", "border": "#1F5C39", "dot": "#4CAF7D"},
    "DPM 2009": {"bg": "#3A2A12", "fg": "#E0B36A", "border": "#5C451F", "dot": "#C98B27"},
    "DAP 2020": {"bg": "#12283A", "fg": "#7FB8D6", "border": "#1F455C", "dot": "#4C8FAF"},
    "Draft DAP 2026": {"bg": "#3A1212", "fg": "#D67F7F", "border": "#5C1F1F", "dot": "#AF4C4C"},
}
NEUTRAL_STYLE = {"bg": "#1C2432", "fg": "#B9C6DA", "border": "#2C3B52", "dot": "#63748F"}

SUGGESTIONS = [
    "What is the delivery schedule for defence contracts under DPM 2025?",
    "Under DAP 2020, what weapons or platforms are banned for import?",
    "Is the draft DAP 2026 currently in force?",
]

app = Flask(__name__)

print("Building retriever and LLM (once, at startup)...")
_retriever = build_hybrid_retriever()
_llm = build_llm()
print("Ready.")


def regime_style_for(doc_name: str) -> dict:
    lowered = doc_name.lower()
    if "draft dap 2026" in lowered:
        return {"label": "Draft DAP 2026", **REGIME_STYLES["Draft DAP 2026"], "is_draft": True}
    if "dpm 2009" in lowered:
        return {"label": "DPM 2009", **REGIME_STYLES["DPM 2009"], "is_draft": False}
    if "dpm 2025" in lowered:
        return {"label": "DPM 2025", **REGIME_STYLES["DPM 2025"], "is_draft": False}
    if "dap 2020" in lowered:
        return {"label": "DAP 2020", **REGIME_STYLES["DAP 2020"], "is_draft": False}
    return {"label": doc_name, **NEUTRAL_STYLE, "is_draft": False}


def extract_citations(answer: str) -> list[dict]:
    """Distinct [doc_name, chapter, para] citations found in the answer, each
    tagged with a regime badge style. Deduped on the full citation (so two
    different paragraphs cited from the same document each get their own
    card), not just on doc_name. Order of first appearance is kept."""
    seen = {}
    for match in CITATION_PATTERN.finditer(answer):
        raw = match.group(0)[1:-1]
        if raw in seen:
            continue
        parts = [p.strip() for p in raw.split(",")]
        doc_name = parts[0] if parts else raw
        seen[raw] = {
            "doc_name": doc_name,
            "reference": ", ".join(parts[1:]) if len(parts) > 1 else "",
            "style": regime_style_for(doc_name),
        }
    return list(seen.values())


def regime_badges(citations: list[dict]) -> list[dict]:
    """One badge per distinct regime actually cited (not per citation)."""
    seen_labels = {}
    for citation in citations:
        style = citation["style"]
        if style["label"] not in seen_labels:
            seen_labels[style["label"]] = style
    return list(seen_labels.values())


def check_auth(auth) -> bool:
    if auth is None or auth.password is None:
        return False
    return secrets.compare_digest(auth.password, SHARED_PASSWORD)


@app.route("/", methods=["GET", "POST"])
def index():
    auth = request.authorization
    if not check_auth(auth):
        return Response(
            "Authentication required.",
            401,
            {"WWW-Authenticate": 'Basic realm="Defence Procurement Knowledge Base"'},
        )

    question = ""
    answer = None
    citations = []
    badges = []

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            answer = answer_question(question, _retriever, _llm)
            citations = extract_citations(answer)
            badges = regime_badges(citations)

    return render_template(
        "index.html",
        question=question,
        answer=answer,
        citations=citations,
        badges=badges,
        suggestions=SUGGESTIONS,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
