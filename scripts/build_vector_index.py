"""
Embeds every chunk in chunked/chunks.jsonl with VoyageAI (voyage-law-2, a model
tuned for legal/regulatory text) and stores the vectors + metadata in a
persistent Chroma collection at chroma_store/.

Idempotent: each chunk gets a stable id derived from its source file and
position (sha1 of "source_file::chunk_index"). Re-running the script skips
any id already present in the collection instead of re-embedding (and
re-paying for) it - safe to re-run after an interruption or after adding new
chunks to the JSONL later.

Requires VOYAGE_API_KEY in config/.env.

Run it from the project root with:
    .venv\\Scripts\\python.exe scripts\\build_vector_index.py
"""

import time
from pathlib import Path

import chromadb
from dotenv import load_dotenv
import os
import voyageai

from llama_index.embeddings.voyageai import VoyageEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from chunk_utils import load_all_nodes

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_store"
COLLECTION_NAME = "defence_kb"
EMBED_MODEL_NAME = "voyage-law-2"

# This Voyage account has no payment method on file, which caps it at 3
# requests/minute and 10K tokens/minute. Keep batches small enough to fit
# under the token cap, and pace requests to stay under the request cap -
# both are enforced below regardless of which tier the account is on, so
# this stays correct if the account is later upgraded (just conservative).
EMBED_BATCH_SIZE = 25
MIN_SECONDS_BETWEEN_REQUESTS = 21
MAX_RETRIES = 5


def main() -> None:
    load_dotenv(PROJECT_ROOT / "config" / ".env")
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        raise SystemExit("VOYAGE_API_KEY not set in config/.env")

    nodes = load_all_nodes()
    print(f"Loaded {len(nodes)} chunks")

    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = chroma_client.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=collection)

    existing_ids = set(collection.get(include=[])["ids"])
    print(f"Collection '{COLLECTION_NAME}' already has {len(existing_ids)} embedded chunk(s).")

    new_nodes = [n for n in nodes if n.id_ not in existing_ids]
    skipped = len(nodes) - len(new_nodes)

    print(f"To embed this run: {len(new_nodes)}  (skipping {skipped} already present)\n")

    if not new_nodes:
        print("Nothing new to embed.")
    else:
        embed_model = VoyageEmbedding(
            model_name=EMBED_MODEL_NAME,
            voyage_api_key=api_key,
            embed_batch_size=EMBED_BATCH_SIZE,
        )

        embedded = 0
        failed = 0
        num_batches = (len(new_nodes) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
        est_minutes = num_batches * MIN_SECONDS_BETWEEN_REQUESTS / 60
        print(f"Pacing at 1 request per {MIN_SECONDS_BETWEEN_REQUESTS}s -> "
              f"~{est_minutes:.0f} min for {num_batches} batches.\n")

        for batch_num, start in enumerate(range(0, len(new_nodes), EMBED_BATCH_SIZE), start=1):
            request_start = time.monotonic()
            batch = new_nodes[start : start + EMBED_BATCH_SIZE]
            print(f"[{batch_num}/{num_batches}] embedding {len(batch)} chunk(s)...", end=" ", flush=True)

            texts = [n.get_content() for n in batch]
            backoff = MIN_SECONDS_BETWEEN_REQUESTS
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    vectors = embed_model.get_text_embedding_batch(texts, show_progress=False)
                    for node, vector in zip(batch, vectors):
                        node.embedding = vector
                    vector_store.add(batch)
                    embedded += len(batch)
                    print("done")
                    break
                except voyageai.error.RateLimitError:
                    if attempt == MAX_RETRIES:
                        failed += len(batch)
                        print(f"FAILED: rate-limited after {MAX_RETRIES} attempts")
                        break
                    print(f"rate-limited, waiting {backoff}s (attempt {attempt}/{MAX_RETRIES})...", end=" ", flush=True)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 120)
                except Exception as exc:
                    failed += len(batch)
                    print(f"FAILED: {exc}")
                    break

            elapsed = time.monotonic() - request_start
            remaining_pause = MIN_SECONDS_BETWEEN_REQUESTS - elapsed
            if remaining_pause > 0 and batch_num < num_batches:
                time.sleep(remaining_pause)

        print("\n--- Summary ---")
        print(f"Embedded: {embedded}")
        print(f"Skipped (already present): {skipped}")
        print(f"Failed: {failed}")

    total_count = collection.count()
    print(f"Collection '{COLLECTION_NAME}' now has {total_count} chunk(s) total.")

    if total_count == 0:
        print("\nSkipping smoke test query - collection is empty.")
        return

    print("\n--- Smoke test query: 'weapons platforms banned for import' ---")
    query_embed_model = VoyageEmbedding(model_name=EMBED_MODEL_NAME, voyage_api_key=api_key)

    backoff = MIN_SECONDS_BETWEEN_REQUESTS
    query_vector = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            query_vector = query_embed_model.get_query_embedding("weapons platforms banned for import")
            break
        except voyageai.error.RateLimitError:
            if attempt == MAX_RETRIES:
                print(f"Smoke test skipped - still rate-limited after {MAX_RETRIES} attempts.")
                return
            print(f"rate-limited, waiting {backoff}s (attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 120)

    results = collection.query(query_embeddings=[query_vector], n_results=3)
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        text = results["documents"][0][i]
        print(f"\n#{i+1}  doc_name={meta.get('doc_name')!r}  chapter={meta.get('chapter')!r}  para={meta.get('para')!r}")
        print(text[:250].replace("\n", " | "))


if __name__ == "__main__":
    main()
