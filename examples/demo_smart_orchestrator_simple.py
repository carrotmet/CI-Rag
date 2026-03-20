"""
Smart Orchestrator Demo - Simplified version
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ci_architecture.orchestrator import (
    SmartOrchestrator,
    Zone
)


def demo_all():
    """Run all demos"""
    print("Smart Orchestrator Demo")
    print("=" * 50)
    
    orchestrator = SmartOrchestrator()
    
    # Demo 1: Zone D to C
    print("\n[Demo 1] Zone D -> Zone C (Info Completion)")
    result = orchestrator.process("How to use this medicine?", session_id="demo1")
    print(f"  Query: 'How to use this medicine?'")
    print(f"  Status: {result['status']}")
    print(f"  Zone: {result.get('current_zone', 'N/A')} -> {result.get('target_zone', 'N/A')}")
    
    if result['status'] == 'clarification_needed':
        print(f"  Missing info: {len(result['missing_info'])} items")
        # Continue with info
        result2 = orchestrator.continue_with_info("demo1", {
            "medicine": "Amoxicillin",
            "age": "35"
        })
        print(f"  After info: Status={result2['status']}, Zone={result2.get('zone', 'N/A')}")
        if result2['status'] == 'success':
            print(f"  CI: C={result2['ci']['C']:.2f}, I={result2['ci']['I']:.2f}")
    
    # Demo 2: Zone B to A
    print("\n[Demo 2] Zone B -> Zone A (Preserve Complexity)")
    result = orchestrator.process("Analyze symptoms and recommend treatment", session_id="demo2")
    print(f"  Query: 'Analyze symptoms and recommend treatment'")
    print(f"  Status: {result['status']}, Zone: {result.get('current_zone', 'N/A')}")
    
    if result['status'] == 'clarification_needed':
        result2 = orchestrator.continue_with_info("demo2", {
            "symptoms": "cough, fever",
            "duration": "3 days"
        })
        print(f"  After info: Status={result2['status']}, Zone={result2.get('zone', 'N/A')}")
    
    # Demo 3: Decomposition
    print("\n[Demo 3] Zone B -> Zone C (Decomposition)")
    result = orchestrator.process(
        "How to design a high-concurrency e-commerce system?",
        session_id="demo3",
        force_zone=Zone.C
    )
    print(f"  Query: 'How to design a high-concurrency e-commerce system?'")
    print(f"  Status: {result['status']}")
    if result['status'] == 'decomposition_proposed':
        print(f"  Sub-problems: {len(result['sub_problems'])}")
        for sp in result['sub_problems']:
            print(f"    - {sp['id']}: {sp['query'][:40]}...")
    
    # Demo 4: Direct optimal
    print("\n[Demo 4] Direct Optimal Zone")
    result = orchestrator.process("What is Python list comprehension?")
    print(f"  Query: 'What is Python list comprehension?'")
    print(f"  Status: {result['status']}, Zone: {result.get('zone', 'N/A')}")
    print(f"  CI: C={result['ci']['C']:.2f}, I={result['ci']['I']:.2f}")
    
    # Demo 5: History
    print("\n[Demo 5] CI History Tracking")
    history = orchestrator.get_session_history("demo1")
    print(f"  Session demo1 has {len(history)} CI evaluations")
    for i, h in enumerate(history, 1):
        print(f"    {i}. Zone {h['zone']}: C={h['C']:.2f}, I={h['I']:.2f}")
    
    print("\n" + "=" * 50)
    print("Demo completed!")


if __name__ == "__main__":
    demo_all()
