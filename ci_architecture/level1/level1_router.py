"""Level 1 Router: Hybrid Retrieval Verification.

Integrates vector semantic search and keyword retrieval for
information sufficiency verification.
"""

import os
from typing import Dict, List, Optional
from dataclasses import asdict

from .vector_retriever import VectorRetriever
from .keyword_retriever import KeywordRetriever
from .structured_retriever import StructuredRetriever
from .fusion import ConfidenceFusion


class Level1Router:
    """
    Level 1: Multi-Source Hybrid Retrieval Router.
    
    Executes parallel retrieval:
    1. Vector semantic search (sentence-transformers + FAISS)
    2. Keyword sparse retrieval (jieba + BM25)
    3. Structured data retrieval (intent + schema matching)
    4. Confidence fusion with conflict detection
    
    Target latency: ~50ms total
    """
    
    def __init__(self,
                 vector_index_path: str = None,
                 keyword_index_path: str = None,
                 documents: List[Dict] = None):
        """
        Initialize Level 1 router.
        
        Args:
            vector_index_path: Path to FAISS index
            keyword_index_path: Path to keyword index (optional)
            documents: List of documents to index (if no saved index)
        """
        self.vector_retriever: Optional[VectorRetriever] = None
        self.keyword_retriever: Optional[KeywordRetriever] = None
        self.structured_retriever: Optional[StructuredRetriever] = None
        self.fusion = ConfidenceFusion()
        
        # Initialize retrievers
        self._init_retrievers(vector_index_path, keyword_index_path, documents)
    
    def _init_retrievers(self, vector_path, keyword_path, documents):
        """Initialize retrieval components."""
        # Vector retriever
        if vector_path and os.path.exists(vector_path):
            try:
                self.vector_retriever = VectorRetriever(index_path=vector_path)
                print(f"Loaded vector index: {vector_path}")
            except Exception as e:
                print(f"Warning: Failed to load vector index: {e}")
        elif documents:
            try:
                self.vector_retriever = VectorRetriever(documents=documents)
                print(f"Built vector index with {len(documents)} documents")
            except Exception as e:
                print(f"Warning: Failed to build vector index: {e}")
        
        # Keyword retriever
        if documents:
            try:
                self.keyword_retriever = KeywordRetriever()
                self.keyword_retriever.add_documents(documents)
                print(f"Built keyword index with {len(documents)} documents")
            except Exception as e:
                print(f"Warning: Failed to build keyword index: {e}")
        
        # Structured retriever
        if documents:
            try:
                self.structured_retriever = StructuredRetriever(documents)
                print(f"Built structured index with {len(documents)} documents")
            except Exception as e:
                print(f"Warning: Failed to build structured index: {e}")
    
    def is_ready(self) -> bool:
        """Check if router is ready for retrieval."""
        return any([
            self.vector_retriever is not None,
            self.keyword_retriever is not None,
            self.structured_retriever is not None
        ])
    
    def retrieve(self, query: str, k: int = 10) -> Dict:
        """
        Execute hybrid retrieval.
        
        Args:
            query: Query string
            k: Number of results per source
            
        Returns:
            Dict with retrieval results and fused confidence
        """
        # Vector retrieval
        vector_result = None
        if self.vector_retriever:
            try:
                v_result = self.vector_retriever.search(query, k=k)
                vector_result = {
                    'sim_max': v_result.sim_max,
                    'gap': v_result.gap,
                    'entropy': v_result.entropy,
                    'results': v_result.results,
                    'raw_scores': v_result.raw_scores
                }
            except Exception as e:
                print(f"Vector retrieval error: {e}")
        
        # Keyword retrieval
        keyword_result = None
        if self.keyword_retriever:
            try:
                k_result = self.keyword_retriever.search(query, top_k=k)
                keyword_result = {
                    'score_max': k_result.score_max,
                    'coverage': k_result.coverage,
                    'results': k_result.results,
                    'matched_terms': k_result.matched_terms
                }
            except Exception as e:
                print(f"Keyword retrieval error: {e}")
        
        # Structured retrieval
        structured_result = None
        if self.structured_retriever:
            try:
                s_result = self.structured_retriever.search(query)
                structured_result = {
                    'schema_match_rate': s_result.schema_match_rate,
                    'row_count': s_result.row_count,
                    'null_ratio': s_result.null_ratio,
                    'success': s_result.success,
                    'results': s_result.results
                }
            except Exception as e:
                print(f"Structured retrieval error: {e}")
        
        # Fusion
        fusion_result = self.fusion.fuse(vector_result, keyword_result, structured_result)
        
        return {
            'I_mean': fusion_result.I_mean,
            'sigma_I': fusion_result.sigma_I,
            'vector': vector_result,
            'keyword': keyword_result,
            'conflict_detected': fusion_result.conflict_detected,
            'source_weights': fusion_result.source_weights
        }
    
    def verify(self, query: str, level0_result: Dict, k: int = 10) -> Dict:
        """
        Verify and refine Level 0 result with retrieval evidence.
        
        Args:
            query: Query string
            level0_result: Result from Level 0
            k: Number of retrieval results
            
        Returns:
            Updated CI result with retrieval evidence
        """
        # Execute retrieval
        retrieval = self.retrieve(query, k=k)
        
        # Fuse with Level 0
        final_result = self.fusion.fuse_with_level0(
            level0_result,
            retrieval.get('vector'),
            retrieval.get('keyword')
        )
        
        # Add provenance
        final_result['retrieval_evidence'] = {
            'vector': retrieval.get('vector'),
            'keyword': retrieval.get('keyword'),
            'top_documents': self._extract_top_documents(retrieval)
        }
        
        return final_result
    
    def _extract_top_documents(self, retrieval: Dict) -> List[Dict]:
        """Extract top documents from retrieval results."""
        docs = []
        
        # From vector results
        vector_results = retrieval.get('vector', {}).get('results', [])
        for i, r in enumerate(vector_results[:3]):
            docs.append({
                'source': 'vector',
                'rank': i + 1,
                'content': r.get('content', ''),
                'score': r.get('similarity', 0.0)
            })
        
        # From keyword results
        keyword_results = retrieval.get('keyword', {}).get('results', [])
        for i, r in enumerate(keyword_results[:3]):
            docs.append({
                'source': 'keyword',
                'rank': i + 1,
                'content': r.get('content', ''),
                'score': r.get('score', 0.0),
                'matched_terms': r.get('matched_terms', [])
            })
        
        return docs
    
    def save_indexes(self, vector_path: str, keyword_path: str = None):
        """Save indexes to disk."""
        if self.vector_retriever and vector_path:
            self.vector_retriever.save_index(vector_path)
            print(f"Saved vector index to: {vector_path}")
        
        # Keyword index serialization would go here
    
    def get_stats(self) -> Dict:
        """Get router statistics."""
        stats = {
            'vector_ready': self.vector_retriever is not None,
            'keyword_ready': self.keyword_retriever is not None,
        }
        
        if self.vector_retriever:
            stats['vector'] = self.vector_retriever.get_stats()
        
        if self.keyword_retriever:
            stats['keyword'] = self.keyword_retriever.get_stats()
        
        return stats


# Convenience function
def verify_with_retrieval(query: str, 
                         level0_result: Dict,
                         vector_index_path: str = None,
                         documents: List[Dict] = None) -> Dict:
    """
    Convenience function for one-off verification.
    
    Args:
        query: Query string
        level0_result: Level 0 result
        vector_index_path: Path to vector index
        documents: Documents to index (if no saved index)
        
    Returns:
        Verified result
    """
    router = Level1Router(
        vector_index_path=vector_index_path,
        documents=documents
    )
    return router.verify(query, level0_result)
