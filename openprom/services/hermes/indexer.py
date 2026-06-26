"""Indexer for the Hermes poetry knowledge layer.

Handles normalization, chunking (whole poem / couplet / quatrain), deduplication,
and batched upsert into the vector store.
"""

import logging
from typing import Any, Dict, List, Optional

from openprom.services.rag.vector_store import PoetryVectorStore, get_vector_store

logger = logging.getLogger(__name__)

BATCH_SIZE = 128


class PoetryIndexer:
    """Index classical poems into the Hermes vector store."""

    def __init__(self, store: Optional[PoetryVectorStore] = None):
        self.store = store or get_vector_store()

    @staticmethod
    def normalize_record(item: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
        """Normalize a poem record to the store schema."""
        poem_id = item.get("id") or item.get("rank") or f"poem_{idx}"
        title = item.get("title", "")
        author = item.get("author", "")
        dynasty = item.get("dynasty", "")
        form = item.get("form", "")
        tags = item.get("tags", [])
        theme = item.get("theme", "")

        text = item.get("text") or item.get("content") or item.get("paragraphs")
        if isinstance(text, list):
            text = "\n".join(text)
        if not text:
            return None

        return {
            "id": str(poem_id),
            "title": title,
            "author": author,
            "dynasty": dynasty,
            "form": form,
            "tags": tags if isinstance(tags, list) else [],
            "theme": theme,
            "text": text.strip(),
        }

    @staticmethod
    def chunk_record(record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split a poem into whole-poem and sub-chunk records.

        Chunks help retrieval granularity: couplets for couplet generation,
        quatrains for jueju inspiration, whole poems for lüshi context.
        """
        lines = [ln.strip() for ln in record["text"].split("\n") if ln.strip()]
        base_meta = {
            "title": record.get("title", ""),
            "author": record.get("author", ""),
            "dynasty": record.get("dynasty", ""),
            "form": record.get("form", ""),
            "tags": ",".join(record.get("tags", [])),
            "theme": record.get("theme", ""),
        }
        chunks: List[Dict[str, Any]] = []
        poem_id = str(record["id"])

        # Whole poem
        chunks.append(
            {
                "id": poem_id,
                **base_meta,
                "text": "\n".join(lines),
                "chunk_type": "poem",
            }
        )

        # Couplets (pairs of lines)
        for i in range(0, len(lines) - 1, 2):
            chunk_lines = lines[i : i + 2]
            if len(chunk_lines) == 2:
                chunks.append(
                    {
                        "id": f"{poem_id}_couplet_{i}",
                        **base_meta,
                        "text": "\n".join(chunk_lines),
                        "chunk_type": "couplet",
                    }
                )

        # Quatrains (4-line chunks) for 8-line lüshi
        if len(lines) >= 8:
            for start in (0, 4):
                chunk_lines = lines[start : start + 4]
                if len(chunk_lines) == 4:
                    chunks.append(
                        {
                            "id": f"{poem_id}_quatrain_{start}",
                            **base_meta,
                            "text": "\n".join(chunk_lines),
                            "chunk_type": "quatrain",
                        }
                    )

        return chunks

    def index_records(self, records: List[Dict[str, Any]]) -> int:
        """Normalize, chunk, deduplicate and index a list of raw records."""
        normalized = []
        for idx, item in enumerate(records):
            rec = self.normalize_record(item, idx)
            if rec:
                normalized.append(rec)

        all_chunks: List[Dict[str, Any]] = []
        seen_ids: set = set()
        for rec in normalized:
            for chunk in self.chunk_record(rec):
                if chunk["id"] in seen_ids:
                    continue
                seen_ids.add(chunk["id"])
                all_chunks.append(chunk)

        total = 0
        for i in range(0, len(all_chunks), BATCH_SIZE):
            batch = all_chunks[i : i + BATCH_SIZE]
            total += self.store.add_poems(batch)
            logger.info(f"Indexed batch {i // BATCH_SIZE + 1}: {len(batch)} chunks")

        return total

    def index_file(self, path: str) -> int:
        """Index a single JSON file or directory of JSON files."""
        import json
        import os
        from pathlib import Path

        if os.path.isdir(path):
            count = 0
            for p in Path(path).rglob("*.json"):
                try:
                    count += self.index_file(str(p))
                except Exception as e:
                    logger.warning(f"Failed to index {p}: {e}")
            return count

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            records = []
            for author, poems in data.items():
                if isinstance(poems, list):
                    for p in poems:
                        if isinstance(p, dict):
                            p.setdefault("author", author)
                            records.append(p)
                elif isinstance(poems, dict):
                    poems.setdefault("author", author)
                    records.append(poems)
            data = records

        return self.index_records(data)

    def reset(self) -> None:
        """Delete and recreate the collection."""
        self.store.delete_collection()
        # Recreate by ensuring client
        self.store._ensure_client()
