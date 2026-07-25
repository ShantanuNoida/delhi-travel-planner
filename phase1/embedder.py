"""
Embeds chunks using a local sentence-transformers model and stores them in ChromaDB.
Also builds and persists the citation index (chunk_id -> source_url + title).

Why sentence-transformers instead of an API:
  - Grok (xAI) does not expose an embeddings endpoint.
  - paraphrase-multilingual-MiniLM-L12-v2 handles Hindi transliterations natively,
    which directly satisfies EC-1.4 without extra alias engineering.
  - Free, local, no rate limits, no API key required.

Upgrade path for production:
  Change EMBED_MODEL to "intfloat/multilingual-e5-large" for higher accuracy (~560 MB).
"""

import json
import os
import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")
CITATION_INDEX_PATH = os.path.join(DATA_DIR, "citation_index.json")
COLLECTION_NAME = "delhi_travel"

# Multilingual model — 118 MB, fast, good Hindi support (EC-1.4)
# Swap to "intfloat/multilingual-e5-large" for production quality
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 64

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"Loading embedding model: {EMBED_MODEL}  (downloaded once, cached locally)")
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def get_chroma_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def build_citation_index(chunks: list[dict]) -> dict:
    return {
        chunk["chunk_id"]: {
            "source_url":    chunk["source_url"],
            "article_title": chunk["article_title"],
            "source":        chunk["source"],
            "last_modified": chunk["last_modified"],
            "chunk_index":   chunk["chunk_index"],
        }
        for chunk in chunks
    }


def embed_and_store(chunks: list[dict]) -> dict:
    """Embed all chunks and upsert into ChromaDB. Returns the citation index."""
    model = _get_model()
    collection = get_chroma_collection()

    existing_ids = set(collection.get(include=[])["ids"])
    new_chunks = [c for c in chunks if c["chunk_id"] not in existing_ids]

    if not new_chunks:
        print("All chunks already embedded — skipping.")
    else:
        print(f"Embedding {len(new_chunks)} chunks in batches of {BATCH_SIZE}...")
        for i in tqdm(range(0, len(new_chunks), BATCH_SIZE)):
            batch = new_chunks[i : i + BATCH_SIZE]
            texts = [c["text"] for c in batch]
            embeddings = model.encode(texts, show_progress_bar=False).tolist()
            collection.upsert(
                ids=[c["chunk_id"] for c in batch],
                embeddings=embeddings,
                documents=texts,
                metadatas=[
                    {
                        "article_title": c["article_title"],
                        "source_url":    c["source_url"],
                        "source":        c["source"],
                        "last_modified": c["last_modified"],
                        "chunk_index":   c["chunk_index"],
                    }
                    for c in batch
                ],
            )

    citation_index = build_citation_index(chunks)
    with open(CITATION_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(citation_index, f, ensure_ascii=False, indent=2)

    print(f"Citation index saved  -> {CITATION_INDEX_PATH}")
    print(f"Vector store total documents: {collection.count()}")
    return citation_index


def query(text: str, n_results: int = 5) -> list[dict]:
    """Query the vector store. Returns top-K results with citation metadata."""
    model = _get_model()
    collection = get_chroma_collection()

    embedding = model.encode([text]).tolist()[0]
    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append(
            {
                "text":          doc,
                "score":         round(1 - dist, 4),
                "article_title": meta["article_title"],
                "source_url":    meta["source_url"],
                "source":        meta["source"],
                "last_modified": meta["last_modified"],
            }
        )
    return hits


def run(chunks: list[dict] | None = None) -> dict:
    if chunks is None:
        with open(os.path.join(DATA_DIR, "chunks.json"), encoding="utf-8") as f:
            chunks = json.load(f)
    return embed_and_store(chunks)


if __name__ == "__main__":
    run()
