"""Vector store abstraction and ChromaDB implementation.

Wraps the existing PoetryVectorStore from services/rag/vector_store.py
into a protocol-based interface for the knowledge layer.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@runtime_checkable
class VectorStore(Protocol):
    """Abstract vector store interface."""

    def upsert(
        self,
        ids: List[str],
        embeddings: NDArray[np.float32],
        metadatas: List[Dict[str, Any]],
        documents: List[str],
    ) -> int:
        """Upsert vectors. Returns count of upserted items."""
        ...

    def query(
        self,
        embedding: NDArray[np.float32],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query by embedding. Returns list of {id, text, metadata, distance}."""
        ...

    def count(self) -> int:
        """Total number of vectors in the store."""
        ...

    def delete_collection(self) -> None:
        """Delete the entire collection."""
        ...


class ChromaVectorStore:
    """ChromaDB-backed vector store."""

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "poetry_knowledge",
    ):
        self.persist_directory = persist_directory or self._default_persist_dir()
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    @staticmethod
    def _default_persist_dir() -> str:
        return str(Path(__file__).parent.parent.parent / "data" / "vector_store")

    def _ensure_client(self):
        if self._client is not None and self._collection is not None:
            return
        import chromadb
        from chromadb.config import Settings as ChromaSettings

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

    def upsert(
        self,
        ids: List[str],
        embeddings: NDArray[np.float32],
        metadatas: List[Dict[str, Any]],
        documents: List[str],
    ) -> int:
        self._ensure_client()
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings.tolist() if isinstance(embeddings, np.ndarray) else embeddings,
        )
        return len(ids)

    def query(
        self,
        embedding: NDArray[np.float32],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        self._ensure_client()
        kwargs: Dict[str, Any] = {
            "query_embeddings": [
                embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
            ],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if filters:
            kwargs["where"] = filters
        results = self._collection.query(**kwargs)
        items = []
        for i, doc_id in enumerate(results["ids"][0]):
            items.append(
                {
                    "id": doc_id,
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                }
            )
        return items

    def count(self) -> int:
        self._ensure_client()
        return self._collection.count()

    def delete_collection(self) -> None:
        self._ensure_client()
        self._client.delete_collection(self.collection_name)
        self._collection = None


_global_store: Optional[ChromaVectorStore] = None


def get_vector_store(
    persist_directory: Optional[str] = None,
    collection_name: Optional[str] = None,
) -> ChromaVectorStore:
    """Get or create the singleton vector store."""
    global _global_store
    if _global_store is not None:
        return _global_store
    persist_dir = persist_directory or os.getenv("OPENPROM_VECTOR_STORE_DIR")
    collection = collection_name or os.getenv(
        "OPENPROM_VECTOR_STORE_COLLECTION", "poetry_knowledge"
    )
    _global_store = ChromaVectorStore(
        persist_directory=persist_dir,
        collection_name=collection,
    )
    return _global_store


def reset_vector_store() -> None:
    """Reset singleton (for testing)."""
    global _global_store
    _global_store = None
