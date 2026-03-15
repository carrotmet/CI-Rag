#!/usr/bin/env python3
"""
Build Level 1 indexes for medical dataset.

Creates:
1. FAISS vector index (semantic search)
2. Keyword inverted index (BM25)
"""

import os
import sys
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ci_architecture.level1 import VectorRetriever, KeywordRetriever
from data.medical_symptoms import get_medical_dataset


def main():
    print("=" * 60)
    print("Level 1 Index Builder - Medical Dataset")
    print("=" * 60)
    
    # Load dataset
    print("\n1. Loading medical dataset...")
    documents = get_medical_dataset()
    print(f"   Loaded {len(documents)} documents")
    
    # Show categories
    categories = {}
    for d in documents:
        cat = d['metadata']['category']
        categories[cat] = categories.get(cat, 0) + 1
    print(f"   Categories: {len(categories)}")
    for cat, count in sorted(categories.items()):
        print(f"     - {cat}: {count}")
    
    # Create output directory
    output_dir = "indexes"
    os.makedirs(output_dir, exist_ok=True)
    
    # Build vector index
    print("\n2. Building vector index (FAISS)...")
    print("   This may take a minute for downloading the embedding model...")
    try:
        vector_retriever = VectorRetriever(documents=documents)
        vector_path = os.path.join(output_dir, "medical_vector.faiss")
        vector_retriever.save_index(vector_path)
        print(f"   ✓ Vector index saved: {vector_path}")
        
        # Show stats
        stats = vector_retriever.get_stats()
        print(f"   Stats: {stats}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("   Make sure sentence-transformers and faiss are installed")
        return 1
    
    # Build keyword index
    print("\n3. Building keyword index (jieba + BM25)...")
    try:
        keyword_retriever = KeywordRetriever()
        keyword_retriever.add_documents(documents)
        
        # Save as pickle (simple serialization)
        keyword_path = os.path.join(output_dir, "medical_keyword.pkl")
        with open(keyword_path, 'wb') as f:
            pickle.dump({
                'index': keyword_retriever.index,
                'documents': keyword_retriever.documents,
                'stats': keyword_retriever.get_stats()
            }, f)
        print(f"   ✓ Keyword index saved: {keyword_path}")
        
        # Show stats
        stats = keyword_retriever.get_stats()
        print(f"   Stats: {stats}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return 1
    
    # Test retrieval
    print("\n4. Testing retrieval...")
    test_query = "咳嗽、铁锈色痰、胸痛"
    print(f"   Query: '{test_query}'")
    
    # Vector search
    v_result = vector_retriever.search(test_query, k=3)
    print(f"\n   Vector Results (top 3):")
    for i, r in enumerate(v_result.results, 1):
        print(f"     {i}. [{r['similarity']:.3f}] {r['content'][:60]}...")
    
    # Keyword search
    k_result = keyword_retriever.search(test_query, top_k=3)
    print(f"\n   Keyword Results (top 3):")
    for i, r in enumerate(k_result.results, 1):
        print(f"     {i}. [{r['score']:.2f}] {r['content'][:60]}...")
        if r['matched_terms']:
            print(f"        Matched: {', '.join(r['matched_terms'])}")
    
    print("\n" + "=" * 60)
    print("Index building complete!")
    print(f"Indexes saved in: {output_dir}/")
    print("=" * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
