"""
Sentence-aware chunker with overlap (EC-1.3).
- Splits on sentence boundaries, not token count
- 50-token overlap between consecutive chunks
- Discards chunks shorter than 2 sentences or starting with conjunctions
"""

import hashlib
import json
import os
import re
import nltk

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

CONJUNCTION_STARTS = {"but", "however", "and", "or", "nor", "yet", "so", "although",
                      "though", "because", "since", "while", "whereas"}

TARGET_CHUNK_TOKENS = 400
OVERLAP_TOKENS = 50


def _token_count(text: str) -> int:
    return len(text.split())


def _starts_with_conjunction(text: str) -> bool:
    first_word = text.strip().split()[0].lower().rstrip(",") if text.strip() else ""
    return first_word in CONJUNCTION_STARTS


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping, sentence-aligned chunks."""
    sentences = nltk.sent_tokenize(text)
    if not sentences:
        return []

    chunks = []
    current_sentences = []
    current_tokens = 0
    overlap_buffer = []

    for sent in sentences:
        sent_tokens = _token_count(sent)
        if current_tokens + sent_tokens > TARGET_CHUNK_TOKENS and current_sentences:
            chunk = " ".join(current_sentences).strip()
            if len(current_sentences) >= 2 and not _starts_with_conjunction(chunk):
                chunks.append(chunk)

            # build overlap: take sentences from the end of current chunk
            overlap_sentences = []
            overlap_t = 0
            for s in reversed(current_sentences):
                t = _token_count(s)
                if overlap_t + t <= OVERLAP_TOKENS:
                    overlap_sentences.insert(0, s)
                    overlap_t += t
                else:
                    break

            current_sentences = overlap_sentences + [sent]
            current_tokens = overlap_t + sent_tokens
        else:
            current_sentences.append(sent)
            current_tokens += sent_tokens

    # flush last chunk
    if current_sentences:
        chunk = " ".join(current_sentences).strip()
        if len(current_sentences) >= 2 and not _starts_with_conjunction(chunk):
            chunks.append(chunk)

    return chunks


def build_chunks(articles: list[dict]) -> list[dict]:
    """Convert articles list into a flat list of chunk dicts."""
    all_chunks = []
    for article in articles:
        text = article["text"]
        raw_chunks = chunk_text(text)
        url_hash = hashlib.md5(article["url"].encode()).hexdigest()[:8]
        for i, chunk_text_val in enumerate(raw_chunks):
            chunk_id = f"{article['source']}_{url_hash}_{i}"
            all_chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk_text_val,
                    "chunk_index": i,
                    "article_title": article["title"],
                    "source_url": article["url"],
                    "source": article["source"],
                    "last_modified": article["last_modified"],
                }
            )
    return all_chunks


def save_chunks(chunks: list[dict]) -> str:
    out_path = os.path.join(DATA_DIR, "chunks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"Built {len(chunks)} chunks → {out_path}")
    return out_path


def run(articles: list[dict] | None = None) -> list[dict]:
    if articles is None:
        with open(os.path.join(DATA_DIR, "raw", "articles.json"), encoding="utf-8") as f:
            articles = json.load(f)
    chunks = build_chunks(articles)
    save_chunks(chunks)
    return chunks


if __name__ == "__main__":
    run()
