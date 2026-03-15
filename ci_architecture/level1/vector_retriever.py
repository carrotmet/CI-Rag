"""Vector Memory Retrieval using sentence-transformers + FAISS.

Target latency: 15-25ms for embedding + search.
"""

import os
import pickle
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import numpy as np

# Optional imports
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


@dataclass
class VectorRetrievalResult:
    """Result from vector retrieval."""
    sim_max: float
    gap: float
    entropy: float
    results: List[Dict]
    raw_scores: List[float]
    query_embedding: Optional[np.ndarray] = None


class VectorRetriever:
    """
    Vector-based semantic retrieval using sentence-transformers and FAISS.
    
    Default model: paraphrase-multilingual-MiniLM-L12-v2
    - 384 dimensions
    - Supports 50+ languages including Chinese-English
    - ~5000 queries/sec on CPU
    """
    
    DEFAULT_MODEL = 'paraphrase-multilingual-MiniLM-L12-v2'
    
    def __init__(self,
                 model_name: str = None,
                 index_path: str = None,
                 documents: List[Dict] = None,
                 device: str = 'cpu'):
        """
        Initialize vector retriever.
        
        Args:
            model_name: Sentence transformer model name
            index_path: Path to saved FAISS index
            documents: List of documents with 'content' and optional 'metadata'
            device: 'cpu' or 'cuda'
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers required. Install: pip install sentence-transformers>=2.2.0")
        if not FAISS_AVAILABLE:
            raise ImportError("faiss required. Install: pip install faiss-cpu>=1.7.0")
        
        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = device
        
        # Load encoder
        self.encoder = SentenceTransformer(self.model_name, device=device)
        self.dim = self.encoder.get_sentence_embedding_dimension()
        
        # Initialize or load index
        self.index = None
        self.documents = []
        self.doc_ids = []
        
        if index_path and os.path.exists(index_path):
            self.load_index(index_path)
        elif documents:
            self.documents = documents
            self.doc_ids = list(range(len(documents)))
            self.index = self._build_index([d['content'] for d in documents])
        else:
            # Empty index
            self.index = faiss.IndexFlatIP(self.dim)  # Inner product for cosine similarity
    
    def _build_index(self, texts: List[str], use_ivf: bool = True) -> faiss.Index:
        """Build FAISS index with appropriate type for scale."""
        print(f"Encoding {len(texts)} documents...")
        embeddings = self.encoder.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        
        # Normalize for cosine similarity via inner product
        faiss.normalize_L2(embeddings)
        
        # Choose index type based on collection size
        n = len(texts)
        if use_ivf and n > 100000:
            # IVF for large collections
            nlist = int(4 * np.sqrt(n))
            quantizer = faiss.IndexFlatIP(self.dim)
            index = faiss.IndexIVFFlat(quantizer, self.dim, nlist, faiss.METRIC_INNER_PRODUCT)
            print(f"Training IVFFlat index with {nlist} clusters...")
            index.train(embeddings)
        else:
            # Flat index for small/medium collections (exact search)
            index = faiss.IndexFlatIP(self.dim)
        
        index.add(embeddings)
        print(f"Index built: {n} documents, {self.dim} dimensions")
        
        return index
    
    def search(self, query: str, k: int = 10) -> VectorRetrievalResult:
        """
        Retrieve documents with confidence-relevant metrics.
        
        Args:
            query: Query string
            k: Number of results to retrieve
            
        Returns:
            VectorRetrievalResult with similarity metrics
        """
        # Encode and normalize query
        query_emb = self.encoder.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_emb)
        
        # Search
        scores, indices = self.index.search(query_emb, k)
        scores, indices = scores[0], indices[0]
        
        # Filter valid results (FAISS may return -1 for empty slots)
        valid_mask = indices >= 0
        scores = scores[valid_mask]
        indices = indices[valid_mask]
        
        if len(scores) == 0:
            return VectorRetrievalResult(
                sim_max=0.0,
                gap=0.0,
                entropy=1.0,
                results=[],
                raw_scores=[],
                query_embedding=query_emb[0]
            )
        
        # Core metrics for confidence estimation
        sim_max = float(scores[0])  # Cosine similarity (inner product of normalized vectors)
        gap = float(scores[0] - scores[1]) if len(scores) > 1 else 0.0
        
        # Normalized entropy of similarity distribution
        # Lower entropy = more concentrated relevance
        probs = np.exp(scores - np.max(scores))  # Softmax for numerical stability
        probs = probs / probs.sum()
        entropy = -np.sum(probs * np.log(probs + 1e-10)) / np.log(len(scores) + 1e-10)
        
        # Retrieve document metadata
        results = []
        for idx, score in zip(indices[:5], scores[:5]):  # Top-5 for downstream
            if idx < len(self.documents):
                doc = self.documents[idx]
                results.append({
                    'doc_id': int(idx),
                    'content': doc['content'][:200] + '...' if len(doc['content']) > 200 else doc['content'],
                    'similarity': float(score),
                    'complexity': doc.get('metadata', {}).get('complexity', 0.5),
                    'source': doc.get('metadata', {}).get('source', 'unknown'),
                    'category': doc.get('metadata', {}).get('category', 'general')
                })
        
        return VectorRetrievalResult(
            sim_max=sim_max,
            gap=gap,
            entropy=float(entropy),
            results=results,
            raw_scores=scores.tolist(),
            query_embedding=query_emb[0]
        )
    
    def add_documents(self, documents: List[Dict]) -> None:
        """Add new documents to the index."""
        if not documents:
            return
        
        texts = [d['content'] for d in documents]
        embeddings = self.encoder.encode(texts, convert_to_numpy=True)
        faiss.normalize_L2(embeddings)
        
        self.index.add(embeddings)
        self.documents.extend(documents)
        self.doc_ids.extend(range(len(self.documents) - len(documents), len(self.documents)))
    
    def save_index(self, index_path: str, doc_path: str = None) -> None:
        """Save FAISS index and documents."""
        os.makedirs(os.path.dirname(index_path) or '.', exist_ok=True)
        
        # Save FAISS index
        faiss.write_index(self.index, index_path)
        
        # Save documents
        doc_path = doc_path or index_path.replace('.faiss', '.docs.pkl')
        with open(doc_path, 'wb') as f:
            pickle.dump({
                'documents': self.documents,
                'doc_ids': self.doc_ids,
                'model_name': self.model_name,
                'dim': self.dim
            }, f)
    
    def load_index(self, index_path: str, doc_path: str = None) -> None:
        """Load FAISS index and documents."""
        # Load FAISS index
        self.index = faiss.read_index(index_path)
        
        # Load documents
        doc_path = doc_path or index_path.replace('.faiss', '.docs.pkl')
        if os.path.exists(doc_path):
            with open(doc_path, 'rb') as f:
                data = pickle.load(f)
                self.documents = data['documents']
                self.doc_ids = data.get('doc_ids', list(range(len(self.documents))))
                self.model_name = data.get('model_name', self.model_name)
                self.dim = data.get('dim', self.dim)
        else:
            print(f"Warning: Document file not found: {doc_path}")
    
    def get_stats(self) -> Dict:
        """Get index statistics."""
        return {
            'num_documents': len(self.documents),
            'embedding_dim': self.dim,
            'model_name': self.model_name,
            'index_type': type(self.index).__name__
        }
