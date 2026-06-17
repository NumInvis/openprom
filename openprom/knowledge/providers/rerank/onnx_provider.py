"""ONNX cross-encoder rerank provider.

Uses onnxruntime for inference and transformers for tokenization.
Supports BAAI/bge-reranker-v2-m3 ONNX format with cross-encoder scoring:
  [CLS] query [SEP] doc [SEP] → logits → sigmoid → relevance score.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"
_MAX_LENGTH = 512


class OnnxRerankProvider:
    """ONNX-based cross-encoder reranker.

    Loads an ONNX model directory containing model.onnx plus tokenizer files.
    For each (query, doc) pair, concatenates as ``[CLS] query [SEP] doc [SEP]``,
    runs through the ONNX session, and applies sigmoid to the logit for a
    relevance probability score.
    """

    name = "onnx-rerank"

    def __init__(
        self,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
        max_length: int = _MAX_LENGTH,
    ):
        self.model_name = model_name or os.getenv(
            "OPENPROM_RERANK_MODEL", _DEFAULT_MODEL
        )
        self.model_path = model_path
        self.max_length = max_length
        self._session = None
        self._tokenizer = None

    def _resolve_model_dir(self) -> str:
        if self.model_path:
            return self.model_path
        safe_name = self.model_name.replace("/", "_")
        return os.path.join("models", f"{safe_name}-onnx")

    def _load(self) -> None:
        if self._session is not None:
            return

        import onnxruntime as ort
        from transformers import AutoTokenizer

        model_dir = self._resolve_model_dir()
        logger.info("Loading ONNX rerank model from %s", model_dir)

        onnx_path = os.path.join(model_dir, "model.onnx")
        self._session = ort.InferenceSession(
            onnx_path, providers=["CPUExecutionProvider"]
        )
        self._tokenizer = AutoTokenizer.from_pretrained(model_dir)
        logger.info("ONNX rerank model loaded: %s", model_dir)

    def _sigmoid(self, x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    def rerank(
        self, query: str, docs: List[str], top_k: int = 10
    ) -> List[Tuple[int, float]]:
        """Rerank docs against query using cross-encoder scoring.

        Returns list of (original_index, score) sorted by score descending,
        length <= top_k.
        """
        self._load()

        if not docs:
            return []

        scores: List[Tuple[int, float]] = []
        for idx, doc in enumerate(docs):
            encoded = self._tokenizer(
                query,
                doc,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="np",
            )
            inputs: Dict[str, np.ndarray] = {
                "input_ids": encoded["input_ids"].astype(np.int64),
                "attention_mask": encoded["attention_mask"].astype(np.int64),
            }
            if "token_type_ids" in encoded:
                inputs["token_type_ids"] = encoded["token_type_ids"].astype(np.int64)

            outputs = self._session.run(None, inputs)
            logit = float(outputs[0][0])
            if outputs[0].ndim > 1:
                logit = float(outputs[0][0][0])

            score = self._sigmoid(logit)
            scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
