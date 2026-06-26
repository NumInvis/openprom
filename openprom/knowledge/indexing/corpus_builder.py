"""Corpus builder: full pipeline from raw source to indexed knowledge.

Pipeline: fetch → normalize → enrich → validate → chunk → index

Usage:
    python -m openprom.knowledge.indexing.corpus_builder --source /path/to/chinese-poetry
    python -m openprom.knowledge.indexing.corpus_builder --source /path/to/chinese-poetry/poet.song.*.json
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from openprom.knowledge.indexing.enricher import enrich_batch
from openprom.knowledge.indexing.normalizer import normalize_batch
from openprom.knowledge.indexing.validator import validate_batch

logger = logging.getLogger(__name__)

BATCH_SIZE = 128


def load_source(path: str) -> List[Dict[str, Any]]:
    """Load records from a JSON file or directory of JSON files."""
    p = Path(path)
    if p.is_dir():
        records = []
        for f in sorted(p.rglob("*.json")):
            try:
                records.extend(load_source(str(f)))
            except Exception as e:
                logger.warning(f"Failed to load {f}: {e}")
        return records

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        records = []
        for key, val in data.items():
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        item.setdefault("author", key)
                        records.append(item)
            elif isinstance(val, dict):
                val.setdefault("author", key)
                records.append(val)
        return records

    return []


def chunk_record(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Split a poem into whole-poem and sub-chunk records for indexing."""
    content = record.get("content", "")
    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    base_meta = {
        "title": record.get("title", ""),
        "author": record.get("author", ""),
        "dynasty": record.get("dynasty", ""),
        "form": record.get("form", ""),
        "tags": ",".join(record.get("tags", [])),
        "theme": record.get("theme", ""),
        "source": record.get("source", ""),
        "confidence": record.get("confidence", 0.95),
        "version": record.get("version", ""),
        "rhyme_category": record.get("rhyme_category", ""),
    }
    chunks: List[Dict[str, Any]] = []
    poem_id = str(record["id"])

    # Whole poem
    chunks.append(
        {
            "id": poem_id,
            "text": content,
            "chunk_type": "poem",
            **base_meta,
        }
    )

    # Couplets (pairs of lines)
    for i in range(0, len(lines) - 1, 2):
        chunk_lines = lines[i : i + 2]
        if len(chunk_lines) == 2:
            chunks.append(
                {
                    "id": f"{poem_id}_couplet_{i}",
                    "text": "\n".join(chunk_lines),
                    "chunk_type": "couplet",
                    **base_meta,
                }
            )

    # Quatrains (4-line chunks for 8-line poems)
    if len(lines) >= 8:
        for start in (0, 4):
            chunk_lines = lines[start : start + 4]
            if len(chunk_lines) == 4:
                chunks.append(
                    {
                        "id": f"{poem_id}_quatrain_{start}",
                        "text": "\n".join(chunk_lines),
                        "chunk_type": "quatrain",
                        **base_meta,
                    }
                )

    return chunks


def build_and_index(
    source_path: str,
    version: str = "2026q2-v1",
    reset: bool = False,
) -> int:
    """Full pipeline: load → normalize → enrich → validate → chunk → index.

    Returns total number of chunks indexed.
    """
    from openprom.knowledge.providers import get_embedding_provider
    from openprom.knowledge.providers.vector_store import get_vector_store

    store = get_vector_store()
    embedding_provider = get_embedding_provider()

    if reset:
        logger.info("Resetting vector store...")
        store.delete_collection()

    # Step 1: Load
    logger.info(f"Loading source from {source_path}")
    raw_records = load_source(source_path)
    logger.info(f"Loaded {len(raw_records)} raw records")

    if not raw_records:
        logger.warning("No records to index")
        return 0

    # Step 2: Normalize
    normalized = normalize_batch(raw_records)
    logger.info(f"Normalized {len(normalized)} records")

    # Step 3: Enrich
    enriched = enrich_batch(normalized)
    logger.info(f"Enriched {len(enriched)} records")

    # Tag version
    for rec in enriched:
        rec["version"] = version

    # Step 4: Validate
    valid, quarantine = validate_batch(enriched)
    if quarantine:
        logger.warning(f"{len(quarantine)} records quarantined")

    # Step 5: Chunk
    all_chunks: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for rec in valid:
        for chunk in chunk_record(rec):
            if chunk["id"] in seen_ids:
                continue
            seen_ids.add(chunk["id"])
            all_chunks.append(chunk)
    logger.info(f"Generated {len(all_chunks)} chunks")

    # Step 6: Index (batch embedding + upsert)
    total = 0
    for i in range(0, len(all_chunks), BATCH_SIZE):
        batch = all_chunks[i : i + BATCH_SIZE]
        texts = [c["text"] for c in batch]
        ids = [c["id"] for c in batch]
        metadatas = []
        for c in batch:
            meta = {k: v for k, v in c.items() if k not in ("id", "text")}
            # Ensure all metadata values are ChromaDB-compatible
            for k, v in meta.items():
                if isinstance(v, list):
                    meta[k] = ",".join(str(x) for x in v)
                elif not isinstance(v, (str, int, float, bool)):
                    meta[k] = str(v)
            metadatas.append(meta)

        embeddings = embedding_provider.embed(texts)
        store.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
        total += len(batch)
        logger.info(f"Indexed batch {i // BATCH_SIZE + 1}: {len(batch)} chunks (total: {total})")

    logger.info(f"Indexing complete: {total} chunks indexed")
    return total


def main():
    parser = argparse.ArgumentParser(description="Build and index poetry corpus")
    parser.add_argument("--source", required=True, help="Path to source JSON or directory")
    parser.add_argument("--version", default="2026q2-v1", help="Corpus snapshot version")
    parser.add_argument("--reset", action="store_true", help="Reset vector store before indexing")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    total = build_and_index(args.source, version=args.version, reset=args.reset)
    print(f"\nDone. {total} chunks indexed.")


if __name__ == "__main__":
    main()
