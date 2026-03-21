"""
Comprehensive V4 Architecture Validation
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_ci_state_mapping():
    """Test CI State to Zone mapping"""
    print("\n1. CI State Zone Mapping")
    print("-" * 40)
    
    from ci_architecture.orchestrator.orchestrator_v4 import CIState
    
    test_cases = [
        (0.2, 0.8, 'C'),  # C0I1
        (0.2, 0.3, 'D'),  # C0I0
        (0.7, 0.3, 'B'),  # C1I0
        (0.7, 0.8, 'A'),  # C1I1
    ]
    
    all_passed = True
    for C, I, expected in test_cases:
        ci = CIState(C=C, I=I, sigma_c=0.7, sigma_i=0.7)
        zone = ci.zone
        passed = zone.value == expected
        all_passed = all_passed and passed
        status = "OK" if passed else "FAIL"
        print(f"  C={C}, I={I} -> Zone {zone.value} (expected {expected}) [{status}]")
    
    return all_passed


def test_orchestrator_validation():
    """Test Orchestrator transition validation"""
    print("\n2. Orchestrator Transition Validation")
    print("-" * 40)
    
    from ci_architecture.orchestrator.orchestrator_v4 import OrchestratorV4
    
    orch = OrchestratorV4()
    
    scenarios = [
        ('D', 0.2, 0.8, True),   # Should approve: C=0, I>=0.7
        ('D', 0.2, 0.5, False),  # Should reject: C=0, I<0.7
        ('A', 0.2, 0.8, True),   # Should approve: A->C with good I
        ('B', 0.2, 0.8, True),   # Should approve: B->C with good I
    ]
    
    all_passed = True
    for source, C, I, should_approve in scenarios:
        ci_state = {
            'C': 0 if C < 0.5 else 1,
            'I': 1 if I >= 0.7 else 0,
            'C_continuous': C,
            'I_continuous': I,
            'sigma_c': 0.7,
            'sigma_i': 0.8
        }
        result = orch.request_transition('test', ci_state, source)
        passed = result.success == should_approve
        all_passed = all_passed and passed
        status = "OK" if passed else "FAIL"
        approved = "APPROVED" if result.success else "REJECTED"
        print(f"  {source}->C (C={C}, I={I}): {approved} [{status}]")
    
    return all_passed


def test_zone_handlers():
    """Test Zone Handlers"""
    print("\n3. Zone Handler Execution")
    print("-" * 40)
    
    from ci_architecture.zones.zone_d import ZoneDHandler
    from ci_architecture.zones.zone_a import ZoneAHandler
    from ci_architecture.zones.zone_b import ZoneBHandler
    from ci_architecture.zones.zone_c import ZoneCHandler
    
    all_passed = True
    
    # Zone D
    zd = ZoneDHandler()
    result = zd.enter('test query', {'C': 0, 'I': 0, 'C_continuous': 0.2, 'I_continuous': 0.3})
    passed = len(result.retrieved_info) > 0
    all_passed = all_passed and passed
    print(f"  Zone D: retrieved={len(result.retrieved_info)} docs [{'OK' if passed else 'FAIL'}]")
    
    # Zone A
    za = ZoneAHandler()
    result = za.enter('complex problem', {'C': 1, 'I': 1, 'C_continuous': 0.8, 'I_continuous': 0.9})
    passed = len(result.sub_problems) > 0
    all_passed = all_passed and passed
    print(f"  Zone A: sub_problems={len(result.sub_problems)} [{'OK' if passed else 'FAIL'}]")
    
    # Zone B
    zb = ZoneBHandler()
    result = zb.enter('hybrid query', {'C': 1, 'I': 0, 'C_continuous': 0.7, 'I_continuous': 0.3})
    passed = result.strategy_used in ['retrieve_first', 'decompose_first', 'parallel_retrieve_decompose']
    all_passed = all_passed and passed
    print(f"  Zone B: strategy={result.strategy_used} [{'OK' if passed else 'FAIL'}]")
    
    # Zone C
    zc = ZoneCHandler()
    result = zc.process_direct('simple query')
    passed = len(result.output) > 0 and result.ci_state['C'] == 0
    all_passed = all_passed and passed
    print(f"  Zone C: output_len={len(result.output)} [{'OK' if passed else 'FAIL'}]")
    
    return all_passed


def test_common_components():
    """Test Common Components"""
    print("\n4. Common Components")
    print("-" * 40)
    
    from ci_architecture.common.guide_generator import GuideGenerator
    from ci_architecture.common.strategy_manager import StrategyManager
    from ci_architecture.common.subproblem_queue import SubProblemQueue, SubProblemResult
    
    all_passed = True
    
    # Guide Generator
    gg = GuideGenerator()
    guide = gg.generate('D', 'test', {'C': 0, 'I': 0})
    passed = 'missing_info' in guide and 'recommended' in guide
    all_passed = all_passed and passed
    print(f"  GuideGenerator: items={len(guide['missing_info'])} [{'OK' if passed else 'FAIL'}]")
    
    # Strategy Manager
    sm = StrategyManager()
    s1 = sm.get_initial_strategy('D')
    s2 = sm.upgrade_strategy('D', s1, 'test')
    passed = s1 != s2
    all_passed = all_passed and passed
    print(f"  StrategyManager: {s1}->{s2} [{'OK' if passed else 'FAIL'}]")
    
    # SubProblem Queue
    spq = SubProblemQueue()
    spq.register_parent('p1', ['sp1', 'sp2'])
    spq.put(SubProblemResult('sp1', 'p1', 'q1', 'a1'))
    spq.put(SubProblemResult('sp2', 'p1', 'q2', 'a2'))
    passed = spq.is_complete('p1')
    all_passed = all_passed and passed
    print(f"  SubProblemQueue: complete={spq.is_complete('p1')} [{'OK' if passed else 'FAIL'}]")
    
    return all_passed


def test_pipeline_integration():
    """Test Pipeline Integration"""
    print("\n5. Integration Test")
    print("-" * 40)
    
    from ci_architecture.v4_pipeline import CIRouterPipelineV4
    
    pipeline = CIRouterPipelineV4()
    result = pipeline.process('What is Python?')
    
    passed = result.final_zone == 'C' and len(result.execution_path) > 0
    print(f"  Pipeline: zone={result.final_zone}, steps={len(result.execution_path)} [{'OK' if passed else 'FAIL'}]")
    
    return passed


def test_zone_c_modes():
    """Test Zone C different modes"""
    print("\n6. Zone C Modes")
    print("-" * 40)
    
    from ci_architecture.zones.zone_c import ZoneCHandler, ReasoningStrategy
    from ci_architecture.common.subproblem_queue import SubProblemQueue
    
    all_passed = True
    
    # Mode 1: Direct
    zc = ZoneCHandler()
    result = zc.process_direct('What is AI?', strategy=ReasoningStrategy.CHAIN_OF_THOUGHT)
    passed = result.output is not None and result.metadata.get('mode') == 'direct'
    all_passed = all_passed and passed
    print(f"  Mode 1 (Direct): [{'OK' if passed else 'FAIL'}]")
    
    # Mode 2: Subproblem queue
    queue = SubProblemQueue()
    zc2 = ZoneCHandler(subproblem_queue=queue)
    queue.register_parent('p1', ['sp1', 'sp2'])
    
    r1 = zc2.process_subproblem('p1', 'sp1', 'What is ML?')
    r2 = zc2.process_subproblem('p1', 'sp2', 'What is DL?')
    
    passed = r1.metadata.get('mode') == 'subproblem_waiting' and r2.metadata.get('mode') == 'subproblem_assembled'
    all_passed = all_passed and passed
    print(f"  Mode 2 (Subproblem): [{'OK' if passed else 'FAIL'}]")
    
    # Mode 3: Assembled
    zc3 = ZoneCHandler()
    result = zc3.process_assembled(
        query='Analyze AI',
        sub_results=[{'query': 'q1', 'answer': 'a1'}],
        retrieved_info=[{'content': 'info1'}]
    )
    passed = result.output is not None and result.metadata.get('mode') == 'assembled'
    all_passed = all_passed and passed
    print(f"  Mode 3 (Assembled): [{'OK' if passed else 'FAIL'}]")
    
    return all_passed


def test_strategy_upgrade_flow():
    """Test strategy upgrade flow"""
    print("\n7. Strategy Upgrade Flow")
    print("-" * 40)
    
    from ci_architecture.orchestrator.orchestrator_v4 import OrchestratorV4
    from ci_architecture.zones.zone_d import ZoneDHandler
    from ci_architecture.common import GuideGenerator, StrategyManager
    
    gg = GuideGenerator()
    sm = StrategyManager()
    zd = ZoneDHandler(gg, sm)
    orch = OrchestratorV4({'D': zd})
    
    # Simulate multiple rounds with rejection
    strategies_used = []
    current_strategy = sm.get_initial_strategy('D')
    
    for attempt in range(1, 4):
        result = zd.enter(
            'test query',
            {'C': 0, 'I': 0, 'C_continuous': 0.2, 'I_continuous': 0.3},
            context={'round_number': attempt, 'strategy': current_strategy}
        )
        strategies_used.append(current_strategy)
        
        transition = orch.request_transition('test', result.ci_state, 'D', attempt)
        
        if transition.success:
            print(f"  Attempt {attempt}: {current_strategy} -> APPROVED")
            break
        else:
            print(f"  Attempt {attempt}: {current_strategy} -> REJECTED, upgrading...")
            current_strategy = sm.upgrade_strategy('D', current_strategy, 'rejected')
    
    passed = len(strategies_used) >= 1
    print(f"  Strategies used: {strategies_used} [{'OK' if passed else 'FAIL'}]")
    
    return passed


def main():
    print("=" * 60)
    print("V4 Architecture Comprehensive Validation")
    print("=" * 60)
    
    tests = [
        ("CI State Mapping", test_ci_state_mapping),
        ("Orchestrator Validation", test_orchestrator_validation),
        ("Zone Handlers", test_zone_handlers),
        ("Common Components", test_common_components),
        ("Pipeline Integration", test_pipeline_integration),
        ("Zone C Modes", test_zone_c_modes),
        ("Strategy Upgrade Flow", test_strategy_upgrade_flow),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  ERROR: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
    
    print("-" * 60)
    print(f"Results: {passed_count}/{total_count} passed")
    print("=" * 60)
    
    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)