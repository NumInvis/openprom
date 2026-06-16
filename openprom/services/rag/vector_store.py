"""ChromaDB vector store wrapper for poetry retrieval.

This is the "Hermes skill" equivalent: a local, embeddable vector store that
powers the poetry knowledge layer.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from openprom.services.rag.embeddings import get_embedding_provider

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "poetry_knowledge"


class PoetryVectorStore:
    """Vector store for ancient Chinese poems."""

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = DEFAULT_COLLECTION,
    ):
        self.persist_directory = persist_directory or self._default_persist_dir()
        self.collection_name = collection_name
        self._client: Optional[chromadb.ClientAPI] = None
        self._collection: Optional[chromadb.Collection] = None
        self._embedding_provider = get_embedding_provider()

    @staticmethod
    def _default_persist_dir() -> str:
        from pathlib import Path
        return str(Path(__file__).parent.parent.parent / "data" / "vector_store")

    def _ensure_client(self):
        if self._client is not None and self._collection is not None:
            return
        self._client = chromadb.Client(
            ChromaSettings(
                persist_directory=self.persist_directory,
                anonymized_telemetry=False,
            )
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB collection ready: {self.collection_name}")

    def add_poems(self, poems: List[Dict[str, Any]]) -> int:
        """Index a list of poem records.

        Each poem dict should contain:
          - id: unique identifier
          - text: the poem content (lines separated by \\n)
          - title, author, dynasty: optional metadata
          - tags, theme: optional for filtering
        """
        self._ensure_client()
        if not poems:
            return 0

        ids = [str(p["id"]) for p in poems]
        documents = [p["text"] for p in poems]
        metadatas = [
            {
                "title": p.get("title", ""),
                "author": p.get("author", ""),
                "dynasty": p.get("dynasty", ""),
                "tags": ",".join(p.get("tags", [])),
                "theme": p.get("theme", ""),
                "form": p.get("form", ""),
            }
            for p in poems
        ]

        embeddings = self._embedding_provider.embed(documents)
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return len(poems)

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search poems by semantic similarity."""
        self._ensure_client()
        query_embedding = self._embedding_provider.embed([query])[0]

        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if filters:
            kwargs["where"] = filters

        results = self._collection.query(**kwargs)
        poems = []
        for i, doc_id in enumerate(results["ids"][0]):
            poems.append({
                "id": doc_id,
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return poems

    def count(self) -> int:
        self._ensure_client()
        return self._collection.count()

    def delete_collection(self):
        self._ensure_client()
        self._client.delete_collection(self.collection_name)
        self._collection = None


def get_vector_store() -> PoetryVectorStore:
    """Factory for the default vector store."""
    persist_dir = os.getenv("OPENPROM_VECTOR_STORE_DIR")
    collection = os.getenv("OPENPROM_VECTOR_STORE_COLLECTION", DEFAULT_COLLECTION)
    return PoetryVectorStore(persist_directory=persist_dir, collection_name=collection)
