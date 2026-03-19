"""Level 1: Multi-Source Hybrid Retrieval.

Implements three parallel retrieval modalities:
- Vector semantic search (sentence-transformers + FAISS)
- Keyword sparse retrieval (jieba + BM25)
- Confidence fusion with calibration
"""

from .vector_retriever import VectorRetriever, VectorRetrievalResult
from .keyword_retriever import KeywordRetriever, InvertedIndex
from .structured_retriever import StructuredRetriever, IntentRecognizer, StructuredResult
from .fusion import RetrievalResult
from .fusion_v3 import ConfidenceFusion
from .level1_router import Level1Router

__all__ = [
    "VectorRetriever",
    "VectorRetrievalResult", 
    "KeywordRetriever",
    "InvertedIndex",
    "StructuredRetriever",
    "IntentRecognizer",
    "StructuredResult",
    "ConfidenceFusion",
    "RetrievalResult",
    "Level1Router",
]
