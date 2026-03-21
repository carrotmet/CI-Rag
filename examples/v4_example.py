"""
CI-RAG-Router V4 Usage Example

This example demonstrates the V4 architecture:
- Level 012 escape layer determines initial zone
- Zone handlers (A/B/D) execute autonomously
- Orchestrator validates transitions
- Zone C provides final output
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ci_architecture.v4_pipeline import CIRouterPipelineV4


def main():
    print("=" * 70)
    print("CI-RAG-Router V4 Architecture Demo")
    print("=" * 70)
    
    # Initialize pipeline (without actual routers for demo)
    pipeline = CIRouterPipelineV4()
    
    # Example queries for different zones
    examples = [
        ("什么是Python？", "Simple query → Zone C"),
        ("机器学习的原理是什么？", "Simple but info needed → Zone D → C"),
        ("如何构建一个高并发的微服务架构？", "Complex → Zone A → C"),
        ("分析一下人工智能对软件开发的影响，并提出改进建议。", "Complex hybrid → Zone B → C"),
    ]
    
    for query, description in examples:
        print(f"\n{'='*70}")
        print(f"Query: {query}")
        print(f"Expected flow: {description}")
        print('-' * 70)
        
        # Process through pipeline
        result = pipeline.process(query)
        
        print(f"Final Zone: {result.final_zone}")
        print(f"Execution Path:")
        for step in result.execution_path:
            step_desc = f"  - {step.get('step', 'unknown')}"
            if 'zone' in step:
                step_desc += f" [zone={step['zone']}]"
            if 'action' in step:
                step_desc += f" [action={step['action']}]"
            if 'ci' in step:
                ci = step['ci']
                step_desc += f" [C={ci.get('C', '?')}, I={ci.get('I', '?')}]"
            print(step_desc)
        
        print(f"\nAnswer preview: {result.answer[:100]}...")
        print(f"Latency: {result.latency_ms:.1f}ms")
    
    print("\n" + "=" * 70)
    print("Statistics:")
    stats = pipeline.get_statistics()
    print(f"  Orchestrator transitions: {stats['orchestrator']}")
    print("=" * 70)


def demo_zones():
    """Demonstrate individual zone handlers"""
    print("\n" + "=" * 70)
    print("Individual Zone Handler Demo")
    print("=" * 70)
    
    from ci_architecture.zones import ZoneAHandler, ZoneDHandler, ZoneCHandler
    from ci_architecture.zones.zone_c import ReasoningStrategy
    from ci_architecture.common import GuideGenerator, StrategyManager
    
    guide_gen = GuideGenerator()
    strategy_mgr = StrategyManager()
    
    # Zone D Demo
    print("\n--- Zone D (Information Retrieval) ---")
    zone_d = ZoneDHandler(guide_gen, strategy_mgr)
    result_d = zone_d.enter(
        query="What is machine learning?",
        ci_state={'C': 0, 'I': 0, 'C_continuous': 0.2, 'I_continuous': 0.3},
        context={'round_number': 1}
    )
    print(f"Retrieved {len(result_d.retrieved_info)} documents")
    print(f"New I_continuous: {result_d.ci_state['I_continuous']:.2f}")
    print(f"Strategy used: {result_d.strategy_used}")
    
    # Zone A Demo
    print("\n--- Zone A (Decomposition) ---")
    zone_a = ZoneAHandler(guide_gen, strategy_mgr)
    result_a = zone_a.enter(
        query="How to build a scalable web application?",
        ci_state={'C': 1, 'I': 1, 'C_continuous': 0.8, 'I_continuous': 0.9},
        context={'round_number': 1}
    )
    print(f"Decomposed into {len(result_a.sub_problems)} sub-problems:")
    for sp in result_a.sub_problems:
        print(f"  - [{sp['id']}] {sp['query'][:50]}...")
    print(f"All simple: {result_a.metadata.get('all_simple', False)}")
    
    # Zone C Demo
    print("\n--- Zone C (Brain/Exit) ---")
    zone_c = ZoneCHandler()
    
    # Direct mode
    result_c = zone_c.process_direct(
        query="What is Python?",
        strategy=ReasoningStrategy.CHAIN_OF_THOUGHT
    )
    print(f"Direct mode output: {result_c.output[:80]}...")
    print(f"Strategy level: {result_c.metadata.get('strategy_level', 1)}")


def demo_orchestrator():
    """Demonstrate orchestrator transition validation"""
    print("\n" + "=" * 70)
    print("Orchestrator V4 Demo")
    print("=" * 70)
    
    from ci_architecture.orchestrator.orchestrator_v4 import OrchestratorV4, Zone
    
    orch = OrchestratorV4()
    
    # Test cases
    test_cases = [
        # (source_zone, C, I, expected_result)
        ("D", 0.2, 0.8, "Approved → C"),  # C=0, I>=0.7
        ("D", 0.2, 0.5, "Rejected"),       # C=0, I<0.7
        ("A", 0.2, 0.8, "Approved → C"),  # C=0, I>=0.7 (after decomposition)
        ("B", 0.2, 0.8, "Approved → C"),  # C=0, I>=0.7 (after hybrid processing)
    ]
    
    for source, C, I, expected in test_cases:
        ci_state = {
            'C': 0 if C < 0.5 else 1,
            'I': 1 if I >= 0.7 else 0,
            'C_continuous': C,
            'I_continuous': I,
            'sigma_c': 0.7,
            'sigma_i': 0.8
        }
        
        result = orch.request_transition(
            query="test",
            ci_state=ci_state,
            source_zone=source
        )
        
        status = "APPROVED" if result.success else "REJECTED"
        target = result.target_zone.value if result.target_zone else "N/A"
        
        print(f"\n{source} → C (C={C}, I={I}):")
        print(f"  Expected: {expected}")
        print(f"  Result: {status} → {target}")
        print(f"  Action: {result.action}")
        if result.trigger_strategy_upgrade:
            print(f"  Strategy upgrade triggered!")


if __name__ == "__main__":
    # Run demos
    main()
    demo_zones()
    demo_orchestrator()
    
    print("\n" + "=" * 70)
    print("Demo completed!")
    print("=" * 70)