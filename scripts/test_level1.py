#!/usr/bin/env python3
"""
Test Level 1 hybrid retrieval with medical dataset.

Demonstrates the complementary strengths of:
- Vector retrieval: semantic understanding of symptom descriptions
- Keyword retrieval: precise matching of medical terminology
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ci_architecture.level0 import Level0Router
from ci_architecture.level1 import Level1Router
from data.medical_symptoms import TEST_QUERIES


def format_result(result: dict, elapsed_ms: float) -> str:
    """Format retrieval result for display."""
    lines = []
    lines.append(f"  Time: {elapsed_ms:.2f}ms")
    lines.append(f"  I (Information Sufficiency): {result['I_mean']:.3f}")
    lines.append(f"  σ_I (Confidence): {result['sigma_I']:.3f}")
    
    if result.get('conflict_detected'):
        lines.append(f"  ⚠️  Conflict detected between sources!")
    
    # Vector results
    v_result = result.get('vector')
    if v_result:
        lines.append(f"\n  [Vector Retrieval]")
        lines.append(f"    sim_max: {v_result['sim_max']:.3f}")
        lines.append(f"    gap: {v_result['gap']:.3f}")
        lines.append(f"    entropy: {v_result['entropy']:.3f}")
        lines.append(f"    Top match: {v_result['results'][0]['content'][:50]}..." if v_result['results'] else "    No results")
    
    # Keyword results
    k_result = result.get('keyword')
    if k_result:
        lines.append(f"\n  [Keyword Retrieval]")
        lines.append(f"    score_max: {k_result['score_max']:.2f}")
        lines.append(f"    coverage: {k_result['coverage']:.2f}")
        lines.append(f"    matched_terms: {', '.join(k_result['matched_terms'][:5])}")
        if k_result['results']:
            lines.append(f"    Top match: {k_result['results'][0]['content'][:50]}...")
    
    return '\n'.join(lines)


def main():
    print("=" * 70)
    print("Level 1 Hybrid Retrieval Test - Medical Domain")
    print("=" * 70)
    print("\nThis test demonstrates why both vector and keyword retrieval are needed:")
    print("- Vector: Understands semantic descriptions of symptoms")
    print("- Keyword: Precisely matches specific medical terminology")
    print()
    
    # Check if indexes exist
    vector_index_path = "indexes/medical_vector.faiss"
    if not os.path.exists(vector_index_path):
        print(f"Error: Index not found: {vector_index_path}")
        print("Please run: python scripts/build_level1_index.py")
        return 1
    
    # Initialize routers
    print("Loading indexes...")
    try:
        level1 = Level1Router(vector_index_path=vector_index_path)
        level0 = Level0Router()  # For cold start mode
        print("✓ Indexes loaded\n")
    except Exception as e:
        print(f"Error loading indexes: {e}")
        return 1
    
    # Run test queries
    print("=" * 70)
    print("Test Queries")
    print("=" * 70)
    
    for i, test in enumerate(TEST_QUERIES, 1):
        query = test['query']
        test_type = test['test_type']
        expected = test['expected_disease']
        
        print(f"\n[{i}] Query: \"{query}\"")
        print(f"    Type: {test_type}")
        print(f"    Expected: {expected}")
        print("-" * 50)
        
        # Level 0 routing
        l0_result = level0.route(query)
        print(f"  Level 0: C={l0_result['C']}, I={l0_result['I']}, "
              f"σ_joint={l0_result['sigma_joint']:.3f}, "
              f"escalate={l0_result['escalate']}")
        
        # Level 1 retrieval
        start = time.time()
        l1_result = level1.verify(query, l0_result)
        elapsed = (time.time() - start) * 1000
        
        print(format_result(l1_result, elapsed))
        
        # Show top documents
        docs = l1_result.get('retrieval_evidence', {}).get('top_documents', [])
        if docs:
            print(f"\n  Top Retrieved Documents:")
            for j, doc in enumerate(docs[:3], 1):
                src = doc.get('source', 'unknown')
                score = doc.get('score', 0)
                content = doc.get('content', '')[:60]
                print(f"    {j}. [{src}] ({score:.3f}) {content}...")
    
    # Interactive mode
    print("\n" + "=" * 70)
    print("Interactive Mode (type 'quit' to exit)")
    print("=" * 70)
    
    while True:
        print()
        try:
            query = input("Enter symptom description: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
        
        if not query or query.lower() in ('quit', 'exit', 'q'):
            break
        
        # Process
        l0_result = level0.route(query)
        start = time.time()
        l1_result = level1.verify(query, l0_result)
        elapsed = (time.time() - start) * 1000
        
        # Show simplified result
        print(f"\nResults:")
        print(f"  C (Complexity): {l1_result['C']}")
        print(f"  I (Info Sufficiency): {l1_result['I']:.3f} "
              f"(L0: {l1_result.get('I_level0', 0):.3f}, "
              f"Retrieval: {l1_result.get('I_retrieval', 0):.3f})")
        print(f"  σ_joint: {l1_result['sigma_joint']:.3f}")
        print(f"  Decision: {'ESCALATE to L2' if l1_result['escalate'] else 'ROUTE to Zone ' + level0.get_zone(l1_result['C'], int(l1_result['I'] >= 0.7))}")
        print(f"  Time: {elapsed:.2f}ms")
        
        # Show top document
        docs = l1_result.get('retrieval_evidence', {}).get('top_documents', [])
        if docs:
            top = docs[0]
            print(f"\n  Best Match [{top.get('source', '?')}]: {top.get('content', '')[:100]}...")
    
    print("\nGoodbye!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
