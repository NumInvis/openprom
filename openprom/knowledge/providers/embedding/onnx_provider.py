"""ONNX Runtime embedding provider.

Runs ONNX-exported models locally for faster CPU inference.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class OnnxEmbeddingProvider:
    """ONNX Runtime embedding provider for local inference."""

    name = "onnx"

    def __init__(
        self,
        model_path: Optional[str] = None,
        dim: int = 512,
    ):
        self.model_path = model_path or os.getenv(
            "OPENPROM_ONNX_MODEL_PATH", "models/bge-small-onnx"
        )
        self.dim = dim
        self._session = None
        self._tokenizer = None

    def _load(self):
        if self._session is not None:
            return
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer

            model_dir = Path(self.model_path)
            onnx_file = model_dir / "model.onnx"
            if not onnx_file.exists():
                raise FileNotFoundError(f"ONNX model not found: {onnx_file}")

            logger.info(f"Loading ONNX embedding model from {model_dir}")
            self._session = ort.InferenceSession(str(onnx_file))
            self._tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            raise

    def embed(self, texts: List[str]) -> NDArray[np.float32]:
        self._load()
        encoded = self._tokenizer(
            texts, padding=True, truncation=True, max_length=512, return_tensors="np"
        )
        outputs = self._session.run(None, dict(encoded))
        # Mean pooling over token embeddings
        embeddings = outputs[0]  # (batch, seq_len, hidden)
        attention = encoded["attention_mask"][:, :, np.newaxis]  # (batch, seq_len, 1)
        summed = (embeddings * attention).sum(axis=1)
        counts = attention.sum(axis=1)
        mean_pooled = summed / np.maximum(counts, 1e-9)
        # L2 normalize
        norms = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
        return (mean_pooled / np.maximum(norms, 1e-9)).astype(np.float32)

    def embed_query(self, query: str) -> NDArray[np.float32]:
        return self.embed([query])[0]
