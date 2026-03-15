"""Keyword/Sparse Retrieval using jieba + BM25.

Target latency: 5-10ms for inverted index traversal.
"""

import re
import math
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict

# Optional import
try:
    import jieba
    import jieba.posseg as pseg
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False


@dataclass
class Posting:
    """Posting list entry for inverted index."""
    doc_id: int
    term_freq: int
    positions: List[int] = field(default_factory=list)


@dataclass
class KeywordResult:
    """Result from keyword retrieval."""
    score_max: float
    coverage: float  # Ratio of query terms found
    results: List[Dict]
    matched_terms: List[str]


class InvertedIndex:
    """
    Inverted index with positional information for phrase queries.
    """
    
    def __init__(self):
        self.index: Dict[str, List[Posting]] = defaultdict(list)
        self.doc_lengths: Dict[int, int] = {}
        self.doc_count: int = 0
        self.total_doc_length: int = 0
        self.doc_contents: Dict[int, str] = {}
    
    def add_document(self, doc_id: int, text: str, tokenizer) -> None:
        """Index a document with positional information."""
        tokens = tokenizer(text)
        self.doc_lengths[doc_id] = len(tokens)
        self.doc_count += 1
        self.total_doc_length += len(tokens)
        self.doc_contents[doc_id] = text
        
        # Build position map
        term_positions: Dict[str, List[int]] = defaultdict(list)
        for pos, token in enumerate(tokens):
            term_positions[token].append(pos)
        
        # Create postings
        for term, positions in term_positions.items():
            self.index[term].append(Posting(
                doc_id=doc_id,
                term_freq=len(positions),
                positions=positions
            ))
    
    def get_postings(self, term: str) -> List[Posting]:
        """Retrieve posting list for term."""
        return self.index.get(term, [])
    
    def get_doc_length(self, doc_id: int) -> int:
        """Get document length."""
        return self.doc_lengths.get(doc_id, 0)
    
    def get_avg_doc_length(self) -> float:
        """Get average document length."""
        if self.doc_count == 0:
            return 0.0
        return self.total_doc_length / self.doc_count


class BM25Scorer:
    """BM25 scoring implementation."""
    
    def __init__(self, index: InvertedIndex, k1: float = 1.5, b: float = 0.75):
        self.index = index
        self.k1 = k1
        self.b = b
        self.avg_doc_length = index.get_avg_doc_length()
        self.idf_cache: Dict[str, float] = {}
    
    def idf(self, term: str) -> float:
        """Compute IDF with caching."""
        if term not in self.idf_cache:
            df = len(self.index.get_postings(term))
            # BM25 IDF with smoothing
            n = self.index.doc_count
            self.idf_cache[term] = math.log(
                (n - df + 0.5) / (df + 0.5) + 1.0
            )
        return self.idf_cache[term]
    
    def score_term(self, doc_id: int, term: str, term_freq: int) -> float:
        """Compute BM25 score for single term-document pair."""
        idf = self.idf(term)
        doc_len = self.index.get_doc_length(doc_id)
        
        # BM25 term frequency saturation
        tf_component = (term_freq * (self.k1 + 1)) / (
            term_freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
        )
        
        return idf * tf_component
    
    def score_query(self, query_terms: List[str], doc_id: int) -> float:
        """Score document for full query."""
        total_score = 0.0
        
        for term in query_terms:
            # Find term frequency in document
            doc_tf = 0
            for posting in self.index.get_postings(term):
                if posting.doc_id == doc_id:
                    doc_tf = posting.term_freq
                    break
            
            if doc_tf > 0:
                total_score += self.score_term(doc_id, term, doc_tf)
        
        return total_score


class KeywordRetriever:
    """
    Keyword-based retrieval using jieba tokenization and BM25 scoring.
    
    Supports:
    - Boolean queries (AND/OR)
    - Phrase queries
    - TF-IDF/BM25 scoring
    """
    
    def __init__(self, use_jieba: bool = True):
        """
        Initialize keyword retriever.
        
        Args:
            use_jieba: Whether to use jieba for Chinese tokenization
        """
        self.use_jieba = use_jieba and JIEBA_AVAILABLE
        self.index = InvertedIndex()
        self.scorer = None
        self.documents: List[Dict] = []
        
        # Load custom dictionary if available
        if self.use_jieba and os.path.exists('custom_dict.txt'):
            jieba.load_userdict('custom_dict.txt')
    
    def tokenize(self, text: str, for_search: bool = True) -> List[str]:
        """
        Tokenize text.
        
        Args:
            text: Input text
            for_search: Use search engine mode (more granular)
        """
        if not text:
            return []
        
        # Lowercase and normalize
        text = text.lower().strip()
        
        if self.use_jieba:
            if for_search:
                return list(jieba.cut_for_search(text))
            else:
                return list(jieba.cut(text, cut_all=False))
        else:
            # Simple whitespace tokenization fallback
            return text.split()
    
    def add_documents(self, documents: List[Dict]) -> None:
        """Add documents to the index."""
        for doc_id, doc in enumerate(documents):
            content = doc['content']
            self.index.add_document(doc_id, content, self.tokenize)
        
        self.documents = documents
        self.scorer = BM25Scorer(self.index)
    
    def search(self, query: str, top_k: int = 10) -> KeywordResult:
        """
        Search documents using BM25 scoring.
        
        Args:
            query: Query string
            top_k: Number of top results to return
            
        Returns:
            KeywordResult with scores and matched terms
        """
        if not self.scorer:
            return KeywordResult(score_max=0.0, coverage=0.0, results=[], matched_terms=[])
        
        # Tokenize query
        query_terms = self.tokenize(query)
        unique_terms = list(set(query_terms))
        
        if not unique_terms:
            return KeywordResult(score_max=0.0, coverage=0.0, results=[], matched_terms=[])
        
        # Find candidate documents containing any query term
        candidate_docs: Dict[int, float] = defaultdict(float)
        matched_terms_per_doc: Dict[int, Set[str]] = defaultdict(set)
        
        for term in unique_terms:
            postings = self.index.get_postings(term)
            for posting in postings:
                score = self.scorer.score_term(posting.doc_id, term, posting.term_freq)
                candidate_docs[posting.doc_id] += score
                matched_terms_per_doc[posting.doc_id].add(term)
        
        if not candidate_docs:
            return KeywordResult(score_max=0.0, coverage=0.0, results=[], matched_terms=[])
        
        # Sort by score
        sorted_docs = sorted(candidate_docs.items(), key=lambda x: x[1], reverse=True)
        
        # Calculate metrics
        score_max = sorted_docs[0][1] if sorted_docs else 0.0
        coverage = len([t for t in unique_terms if any(t in m for m in matched_terms_per_doc.values())]) / len(unique_terms)
        
        # Build results
        results = []
        all_matched_terms = set()
        
        for doc_id, score in sorted_docs[:top_k]:
            doc = self.documents[doc_id] if doc_id < len(self.documents) else {'content': ''}
            matched = list(matched_terms_per_doc[doc_id])
            all_matched_terms.update(matched)
            
            results.append({
                'doc_id': doc_id,
                'content': doc['content'][:150] + '...' if len(doc['content']) > 150 else doc['content'],
                'score': float(score),
                'matched_terms': matched,
                'metadata': doc.get('metadata', {})
            })
        
        return KeywordResult(
            score_max=float(score_max),
            coverage=float(coverage),
            results=results,
            matched_terms=list(all_matched_terms)
        )
    
    def boolean_search(self, query_terms: List[str], operator: str = 'AND') -> Set[int]:
        """
        Execute Boolean retrieval.
        
        Args:
            query_terms: List of query terms
            operator: 'AND' or 'OR'
            
        Returns:
            Set of document IDs
        """
        result_sets = []
        for term in query_terms:
            doc_ids = {p.doc_id for p in self.index.get_postings(term)}
            result_sets.append(doc_ids)
        
        if not result_sets:
            return set()
        
        if operator == 'AND':
            return set.intersection(*result_sets)
        else:  # OR
            return set.union(*result_sets)
    
    def phrase_search(self, phrase: str) -> List[int]:
        """
        Exact phrase search with positional verification.
        
        Args:
            phrase: Phrase to search for
            
        Returns:
            List of document IDs containing the exact phrase
        """
        phrase_tokens = self.tokenize(phrase)
        if not phrase_tokens:
            return []
        
        # Get candidate documents containing all terms
        candidates = self.boolean_search(phrase_tokens, 'AND')
        
        # Verify phrase adjacency
        results = []
        for doc_id in candidates:
            # Get positions for each term in document
            term_positions = []
            for term in phrase_tokens:
                positions = []
                for posting in self.index.get_postings(term):
                    if posting.doc_id == doc_id:
                        positions = posting.positions
                        break
                term_positions.append(positions)
            
            if len(term_positions) != len(phrase_tokens):
                continue
            
            # Check for consecutive positions
            for start_pos in term_positions[0]:
                is_phrase = True
                for i, positions in enumerate(term_positions[1:], 1):
                    if start_pos + i not in positions:
                        is_phrase = False
                        break
                if is_phrase:
                    results.append(doc_id)
                    break
        
        return results
    
    def get_stats(self) -> Dict:
        """Get index statistics."""
        vocab_size = len(self.index.index)
        total_postings = sum(len(postings) for postings in self.index.index.values())
        
        return {
            'num_documents': self.index.doc_count,
            'vocabulary_size': vocab_size,
            'total_postings': total_postings,
            'avg_doc_length': self.index.get_avg_doc_length(),
            'tokenizer': 'jieba' if self.use_jieba else 'whitespace'
        }


# For import compatibility
import os
