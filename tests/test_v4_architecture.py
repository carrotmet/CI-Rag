"""
Tests for CI-RAG-Router V4 Architecture

Tests:
- Zone handlers (A, B, D, C)
- Orchestrator V4 (transition validation)
- Pipeline integration
"""

import pytest
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ci_architecture.orchestrator.orchestrator_v4 import (
    OrchestratorV4, Zone, CIState, TransitionResult
)
from ci_architecture.zones import (
    ZoneAHandler, ZoneBHandler, ZoneCHandler, ZoneDHandler, ZoneResult
)
from ci_architecture.zones.base import ZoneType
from ci_architecture.common import (
    GuideGenerator, StrategyManager, SubProblemQueue
)
from ci_architecture.zones.zone_c import ReasoningStrategy


class TestOrchestratorV4:
    """Test Orchestrator V4 transition validation"""
    
    def test_transition_to_c_approved(self):
        """Test transition to Zone C when criteria met"""
        orch = OrchestratorV4()
        
        # C=0, I=0.8 should transition to C
        ci_state = {
            'C': 0,
            'I': 1,
            'C_continuous': 0.2,
            'I_continuous': 0.8,
            'sigma_c': 0.7,
            'sigma_i': 0.8
        }
        
        result = orch.request_transition(
            query="test query",
            ci_state=ci_state,
            source_zone="D"
        )
        
        assert result.success is True
        assert result.target_zone == Zone.C
        assert result.action == "transition_to_c"
    
    def test_transition_rejected(self):
        """Test transition rejection when criteria not met"""
        orch = OrchestratorV4()
        
        # C=0, I=0.5 should NOT transition to C (need I>=0.7)
        ci_state = {
            'C': 0,
            'I': 0,
            'C_continuous': 0.2,
            'I_continuous': 0.5,
            'sigma_c': 0.6,
            'sigma_i': 0.6
        }
        
        result = orch.request_transition(
            query="test query",
            ci_state=ci_state,
            source_zone="D"
        )
        
        assert result.success is False
        assert result.action == "return_to_source"
        assert result.trigger_strategy_upgrade is True
    
    def test_force_transition_after_max_attempts(self):
        """Test force transition after max attempts"""
        orch = OrchestratorV4()
        orch.max_attempts = 3
        
        ci_state = {
            'C': 0,
            'I': 0,
            'C_continuous': 0.2,
            'I_continuous': 0.5,
            'sigma_c': 0.6,
            'sigma_i': 0.6
        }
        
        result = orch.request_transition(
            query="test query",
            ci_state=ci_state,
            source_zone="D",
            attempt_count=3
        )
        
        assert result.success is True
        assert result.force_transition is True
        assert result.target_zone == Zone.C


class TestZoneHandlers:
    """Test Zone Handlers"""
    
    def test_zone_d_retrieval(self):
        """Test Zone D executes retrieval"""
        handler = ZoneDHandler()
        
        result = handler.enter(
            query="test query",
            ci_state={'C': 0, 'I': 0, 'C_continuous': 0.2, 'I_continuous': 0.3},
            guide={'recommended': ['retrieve_vector'], 'missing_info': ['context']},
            context={'round_number': 1}
        )
        
        assert result.zone == ZoneType.D
        assert result.success is True
        assert len(result.retrieved_info) > 0
        assert result.transition_requested is True
    
    def test_zone_a_decomposition(self):
        """Test Zone A executes decomposition"""
        handler = ZoneAHandler()
        
        result = handler.enter(
            query="How to build a scalable web application with microservices?",
            ci_state={'C': 1, 'I': 1, 'C_continuous': 0.8, 'I_continuous': 0.9},
            guide={'recommended': ['decompose_by_step']},
            context={'round_number': 1}
        )
        
        assert result.zone == ZoneType.A
        assert result.success is True
        assert len(result.sub_problems) > 0
        assert result.transition_requested is True
    
    def test_zone_b_hybrid(self):
        """Test Zone B executes hybrid approach"""
        handler = ZoneBHandler()
        
        result = handler.execute_round(
            query="Analyze the impact of AI on software engineering",
            guide={'recommended': ['retrieve_first']},
            context={'round_number': 1}
        )
        
        assert result.zone == ZoneType.B
        assert result.success is True
        assert result.strategy_used in ['retrieve_first', 'decompose_first', 'parallel_retrieve_decompose']
    
    def test_zone_c_direct(self):
        """Test Zone C direct processing"""
        handler = ZoneCHandler()
        
        result = handler.process_direct(
            query="What is Python?",
            strategy=ReasoningStrategy.DIRECT
        )
        
        assert result.zone == ZoneType.C
        assert result.success is True
        assert result.output is not None
        assert result.ci_state['C'] == 0
        assert result.ci_state['I'] == 1
    
    def test_zone_c_subproblem_queue(self):
        """Test Zone C sub-problem queue"""
        queue = SubProblemQueue()
        handler = ZoneCHandler(subproblem_queue=queue)
        
        # Register parent
        parent_id = "test_parent"
        sub_ids = ["sp_1", "sp_2"]
        queue.register_parent(parent_id, sub_ids)
        
        # Process first sub-problem
        result1 = handler.process_subproblem(
            parent_id=parent_id,
            subproblem_id="sp_1",
            query="What is Python?"
        )
        
        # Should be waiting
        assert result1.metadata.get('mode') == 'subproblem_waiting'
        
        # Process second sub-problem
        result2 = handler.process_subproblem(
            parent_id=parent_id,
            subproblem_id="sp_2",
            query="What are Python's main features?"
        )
        
        # Should be assembled
        assert result2.metadata.get('mode') == 'subproblem_assembled'
        assert result2.output is not None


class TestCommonComponents:
    """Test common components"""
    
    def test_guide_generator_default(self):
        """Test GuideGenerator creates default guides"""
        gen = GuideGenerator()
        
        guide = gen.generate(
            zone='D',
            query='test',
            ci_state={'C': 0, 'I': 0}
        )
        
        assert 'missing_info' in guide
        assert 'recommended' in guide
        assert guide['_meta']['zone'] == 'D'
    
    def test_strategy_manager_upgrade(self):
        """Test StrategyManager upgrades strategies"""
        mgr = StrategyManager()
        
        # Get initial strategy
        initial = mgr.get_initial_strategy('D')
        assert initial == 'retrieve_vector'
        
        # Upgrade
        upgraded = mgr.upgrade_strategy('D', initial, 'insufficient_results')
        assert upgraded == 'retrieve_keyword'
        
        # Upgrade again
        upgraded2 = mgr.upgrade_strategy('D', upgraded, 'still_insufficient')
        assert upgraded2 == 'retrieve_hybrid'
    
    def test_strategy_manager_force_transition(self):
        """Test StrategyManager force transition detection"""
        mgr = StrategyManager()
        
        assert mgr.should_force_transition('D', 1) is False
        assert mgr.should_force_transition('D', 2) is False
        assert mgr.should_force_transition('D', 3) is True
        assert mgr.should_force_transition('D', 5) is True
    
    def test_subproblem_queue(self):
        """Test SubProblemQueue"""
        queue = SubProblemQueue()
        
        # Register parent
        queue.register_parent("parent_1", ["sp_1", "sp_2", "sp_3"])
        
        # Check progress
        progress = queue.get_progress("parent_1")
        assert progress['completed'] == 0
        assert progress['expected'] == 3
        assert progress['is_complete'] is False
        
        # Add results
        from ci_architecture.common.subproblem_queue import SubProblemResult
        
        queue.put(SubProblemResult(
            subproblem_id="sp_1",
            parent_id="parent_1",
            query="q1",
            answer="a1"
        ))
        
        queue.put(SubProblemResult(
            subproblem_id="sp_2",
            parent_id="parent_1",
            query="q2",
            answer="a2"
        ))
        
        progress = queue.get_progress("parent_1")
        assert progress['completed'] == 2
        
        # Complete
        queue.put(SubProblemResult(
            subproblem_id="sp_3",
            parent_id="parent_1",
            query="q3",
            answer="a3"
        ))
        
        assert queue.is_complete("parent_1") is True
        
        results = queue.get_all("parent_1")
        assert len(results) == 3


class TestIntegration:
    """Integration tests"""
    
    def test_simple_d_to_c_flow(self):
        """Test simple D → C flow"""
        # Setup
        guide_gen = GuideGenerator()
        strategy_mgr = StrategyManager()
        
        zone_handlers = {
            'D': ZoneDHandler(guide_gen, strategy_mgr),
            'C': ZoneCHandler(guide_gen, strategy_mgr)
        }
        
        orchestrator = OrchestratorV4(zone_handlers)
        
        # Start in D with low I
        zone_d = zone_handlers['D']
        result_d = zone_d.enter(
            query="What is machine learning?",
            ci_state={'C': 0, 'I': 0, 'C_continuous': 0.2, 'I_continuous': 0.3},
            guide=None,
            context={'round_number': 1}
        )
        
        # Request transition (should be rejected initially)
        transition = orchestrator.process_zone_result(result_d, 'D')
        
        if transition.success:
            # Transition to C
            zone_c = zone_handlers['C']
            result_c = zone_c.process_direct(result_d.query)
            
            assert result_c.output is not None
            assert result_c.ci_state['C'] == 0
        else:
            # Would normally retry with upgraded strategy
            assert transition.trigger_strategy_upgrade is True


def run_tests():
    """Run all tests"""
    print("=" * 60)
    print("CI-RAG-Router V4 Architecture Tests")
    print("=" * 60)
    
    # Run tests
    test_classes = [
        TestOrchestratorV4(),
        TestZoneHandlers(),
        TestCommonComponents(),
        TestIntegration()
    ]
    
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print(f"\n{class_name}:")
        print("-" * 40)
        
        for method_name in dir(test_class):
            if method_name.startswith('test_'):
                try:
                    method = getattr(test_class, method_name)
                    method()
                    print(f"  [PASS] {method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  [FAIL] {method_name}: {e}")
                    failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)