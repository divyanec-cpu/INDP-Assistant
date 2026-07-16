"""
Builds a hybrid retriever that combines VoyageAI vector similarity search
(over the existing chroma_store/ collection) with BM25 keyword search (over
the same chunks, loaded fresh from chunked/chunks.jsonl each run - the corpus
is small enough that rebuilding the in-memory BM25 index each time is fast
and avoids a second on-disk artifact that could drift out of sync).

The two retrievers' ranked results are merged with reciprocal rank fusion
(RRF), which combines by rank position rather than raw score - necessary
here because BM25 scores and cosine-similarity scores aren't on comparable
scales. Query expansion (asking an LLM to generate alternate phrasings of
the query) is disabled (num_queries=1): this script only fuses results for
the single query actually given, so it doesn't require an LLM call just to
retrieve.

Requires VOYAGE_API_KEY in config/.env, and an already-populated Chroma
collection (see build_vector_index.py).

Run it from the project root with:
    .venv\\Scripts\\python.exe scripts\\hybrid_retrieve.py
"""

import os
import sys
from pathlib import Path

# Windows' console defaults to a codepage (e.g. cp1252) that can't print
# characters like the Rupee sign (U+20B9) found in the corpus - reconfigure
# stdout to UTF-8 so query results with such characters don't crash the print.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import chromadb
from dotenv import load_dotenv

from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.embeddings.voyageai import VoyageEmbedding
from llama_index.llms.anthropic import Anthropic
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.vector_stores.chroma import ChromaVectorStore

from chunk_utils import load_all_nodes

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_store"
COLLECTION_NAME = "defence_kb"
EMBED_MODEL_NAME = "voyage-law-2"

TEST_QUERIES = [
    "what is the delivery schedule timeframe for defence contracts",
    "₹10 crore",
    "60 days after warranty period",
    "weapons platforms banned for import",
]


def build_hybrid_retriever(similarity_top_k: int = 10) -> QueryFusionRetriever:
    load_dotenv(PROJECT_ROOT / "config" / ".env")
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        raise SystemExit("VOYAGE_API_KEY not set in config/.env")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set in config/.env")

    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    if collection.count() == 0:
        raise SystemExit(
            f"Collection '{COLLECTION_NAME}' is empty - run build_vector_index.py first."
        )
    vector_store = ChromaVectorStore(chroma_collection=collection)
    embed_model = VoyageEmbedding(model_name=EMBED_MODEL_NAME, voyage_api_key=api_key)
    vector_index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
    vector_retriever = vector_index.as_retriever(similarity_top_k=similarity_top_k)

    nodes = load_all_nodes()
    bm25_retriever = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=similarity_top_k)

    # QueryFusionRetriever's constructor resolves an LLM unconditionally (it
    # defaults to OpenAI via a global Settings.llm lookup, which errors here
    # since this project has no OpenAI key). num_queries=1 means it's never
    # actually called for query generation, but passing our real LLM
    # (Anthropic, not OpenAI - see Technical Brief) satisfies the constructor.
    llm = Anthropic(model="claude-sonnet-5", api_key=anthropic_api_key)

    return QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        llm=llm,
        mode=FUSION_MODES.RECIPROCAL_RANK,
        similarity_top_k=similarity_top_k,
        num_queries=1,
        use_async=False,
    )


def main() -> None:
    retriever = build_hybrid_retriever()

    for query in TEST_QUERIES:
        print(f"\n=== Query: {query!r} ===")
        results = retriever.retrieve(query)
        for i, result in enumerate(results[:5], start=1):
            meta = result.node.metadata
            text = result.node.get_content()
            print(f"#{i}  score={result.score:.4f}  doc_name={meta.get('doc_name')!r}  "
                  f"chapter={meta.get('chapter')!r}  para={meta.get('para')!r}")
            print(text[:250].replace("\n", " | "))
            print()


if __name__ == "__main__":
    main()
