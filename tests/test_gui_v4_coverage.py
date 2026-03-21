"""
V4 GUI 测试覆盖验证

验证 GUI 是否覆盖了所有 V4 架构测试点
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_v4_components_import():
    """Test V4 components can be imported"""
    print("\n1. Testing V4 Components Import...")
    
    components = [
        ('ci_architecture.v4_pipeline', 'CIRouterPipelineV4'),
        ('ci_architecture.orchestrator.orchestrator_v4', 'OrchestratorV4'),
        ('ci_architecture.zones', 'ZoneAHandler'),
        ('ci_architecture.zones', 'ZoneBHandler'),
        ('ci_architecture.zones', 'ZoneCHandler'),
        ('ci_architecture.zones', 'ZoneDHandler'),
        ('ci_architecture.common', 'GuideGenerator'),
        ('ci_architecture.common', 'StrategyManager'),
        ('ci_architecture.common', 'SubProblemQueue'),
    ]
    
    all_passed = True
    for module, name in components:
        try:
            exec(f"from {module} import {name}")
            print(f"  [PASS] {module}.{name}")
        except Exception as e:
            print(f"  [FAIL] {module}.{name}: {e}")
            all_passed = False
    
    return all_passed


def test_v4_gui_module():
    """Test V4 GUI module"""
    print("\n2. Testing V4 GUI Module...")
    
    try:
        from tools.ci_test_window_v4 import CIRouterTestWindowV4, V4_AVAILABLE
        print(f"  [PASS] V4 GUI module imported")
        print(f"  [INFO] V4_AVAILABLE: {V4_AVAILABLE}")
        return V4_AVAILABLE
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_v4_functional_coverage():
    """Test all V4 functions work correctly"""
    print("\n3. Testing V4 Functional Coverage...")
    
    from ci_architecture.orchestrator.orchestrator_v4 import OrchestratorV4, CIState, Zone
    from ci_architecture.zones import ZoneAHandler, ZoneBHandler, ZoneCHandler, ZoneDHandler
    from ci_architecture.zones.zone_c import ReasoningStrategy
    from ci_architecture.common import SubProblemQueue
    from ci_architecture.common.subproblem_queue import SubProblemResult
    
    tests = []
    
    # Test 1: CI Mapping
    try:
        ci = CIState(C=0.2, I=0.8, sigma_c=0.7, sigma_i=0.7)
        assert ci.zone == Zone.C
        tests.append(("CI Mapping C0I1->Zone C", True))
    except Exception as e:
        tests.append(("CI Mapping", False))
    
    # Test 2: Orchestrator Transition
    try:
        orch = OrchestratorV4()
        ci_state = {'C': 0, 'I': 1, 'C_continuous': 0.2, 'I_continuous': 0.8, 'sigma_c': 0.7, 'sigma_i': 0.8}
        result = orch.request_transition('test', ci_state, 'D')
        assert result.success is True
        assert result.target_zone == Zone.C
        tests.append(("Orchestrator Transition", True))
    except Exception as e:
        tests.append(("Orchestrator Transition", False))
    
    # Test 3: Zone D Retrieval
    try:
        zd = ZoneDHandler()
        result = zd.enter('test', {'C': 0, 'I': 0, 'C_continuous': 0.2, 'I_continuous': 0.3})
        assert len(result.retrieved_info) > 0
        tests.append(("Zone D Retrieval", True))
    except Exception as e:
        tests.append(("Zone D Retrieval", False))
    
    # Test 4: Zone A Decomposition
    try:
        za = ZoneAHandler()
        result = za.enter('complex problem', {'C': 1, 'I': 1, 'C_continuous': 0.8, 'I_continuous': 0.9})
        assert len(result.sub_problems) > 0
        tests.append(("Zone A Decomposition", True))
    except Exception as e:
        tests.append(("Zone A Decomposition", False))
    
    # Test 5: Zone B Hybrid
    try:
        zb = ZoneBHandler()
        result = zb.enter('hybrid query', {'C': 1, 'I': 0, 'C_continuous': 0.7, 'I_continuous': 0.3})
        assert result.strategy_used in ['retrieve_first', 'decompose_first', 'parallel_retrieve_decompose']
        tests.append(("Zone B Hybrid", True))
    except Exception as e:
        tests.append(("Zone B Hybrid", False))
    
    # Test 6: Zone C Direct Mode
    try:
        zc = ZoneCHandler()
        result = zc.process_direct('test', strategy=ReasoningStrategy.DIRECT)
        assert result.output is not None
        tests.append(("Zone C Direct Mode", True))
    except Exception as e:
        tests.append(("Zone C Direct Mode", False))
    
    # Test 7: Zone C Queue Mode
    try:
        queue = SubProblemQueue()
        zc = ZoneCHandler(subproblem_queue=queue)
        queue.register_parent('p1', ['sp1', 'sp2'])
        zc.process_subproblem('p1', 'sp1', 'q1')
        result = zc.process_subproblem('p1', 'sp2', 'q2')
        assert queue.is_complete('p1')
        tests.append(("Zone C Queue Mode", True))
    except Exception as e:
        tests.append(("Zone C Queue Mode", False))
    
    # Print results
    all_passed = True
    for name, passed in tests:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        all_passed = all_passed and passed
    
    return all_passed


def test_gui_button_coverage():
    """Test all GUI buttons are properly configured"""
    print("\n4. Testing GUI Button Coverage...")
    
    expected_buttons = [
        "CI映射",
        "Zone D检索",
        "Zone A拆解",
        "Zone B混合",
        "Zone C直接",
        "Zone C队列",
        "策略升级",
        "转区校验",
    ]
    
    from tools.ci_test_window_v4 import CIRouterTestWindowV4
    
    # Check methods exist
    methods = [
        'test_ci_mapping',
        'test_zone_d',
        'test_zone_a',
        'test_zone_b',
        'test_zone_c_direct',
        'test_zone_c_queue',
        'test_strategy_upgrade',
        'test_transition_validation',
    ]
    
    all_exist = True
    for method in methods:
        exists = hasattr(CIRouterTestWindowV4, method)
        status = "PASS" if exists else "FAIL"
        print(f"  [{status}] Method: {method}")
        all_exist = all_exist and exists
    
    return all_exist


def test_tab_coverage():
    """Test all required tab methods are present"""
    print("\n5. Testing Tab Coverage...")
    
    expected_methods = [
        'build_summary_tab',
        'build_v4_pipeline_tab',
        'build_zone_execution_tab',
        'build_features_tab',
        'build_retrieval_tab',
        'build_level2_tab',
        'build_orchestrator_v4_tab',
        'build_orchestrator_tab',
        'build_json_tab',
        'build_history_tab',
    ]
    
    from tools.ci_test_window_v4 import CIRouterTestWindowV4
    
    all_exist = True
    for method in expected_methods:
        exists = hasattr(CIRouterTestWindowV4, method)
        status = "PASS" if exists else "FAIL"
        print(f"  [{status}] Tab Method: {method}")
        all_exist = all_exist and exists
    
    return all_exist


def main():
    """Run all tests"""
    print("=" * 60)
    print("V4 GUI Test Coverage Verification")
    print("=" * 60)
    
    tests = [
        ("V4 Components Import", test_v4_components_import),
        ("V4 GUI Module", test_v4_gui_module),
        ("V4 Functional Coverage", test_v4_functional_coverage),
        ("GUI Button Coverage", test_gui_button_coverage),
        ("Tab Coverage", test_tab_coverage),
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
    print("Test Coverage Summary")
    print("=" * 60)
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
    
    print("-" * 60)
    print(f"Results: {passed_count}/{total_count} passed")
    
    if passed_count == total_count:
        print("\n[OK] All V4 GUI test points covered!")
    
    print("=" * 60)
    
    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)