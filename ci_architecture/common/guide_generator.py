"""
Public Guide Generator for V4 architecture.

Guide is a public resource that any zone can use.
Implements light-weight L2 call (~50ms) for guide generation.
"""

from typing import Dict, List, Optional, Any
import time


class GuideGenerator:
    """
    Public guide generator used by all zones.
    
    V4 Architecture:
    - Guide is generated via light-weight L2 call
    - Zones call this internally when guide is missing
    - Orchestrator does NOT generate guides
    """
    
    def __init__(self, l2_router=None):
        """
        Args:
            l2_router: Level2 router instance for light guide generation
        """
        self.l2_router = l2_router
        
    def generate(self, zone: str, query: str, ci_state: Dict) -> Dict:
        """
        Generate orchestrator guide for a zone.
        
        Args:
            zone: Target zone (A/B/C/D)
            query: User query
            ci_state: Current CI state dict with C, I, sigma_c, sigma_i
            
        Returns:
            Guide dict with missing_info, recommended, etc.
        """
        start_time = time.time()
        
        # If L2 router available, use light guide generation
        if self.l2_router and hasattr(self.l2_router, 'generate_orchestrator_guide'):
            try:
                level0_result = {
                    'C': ci_state.get('C', 0),
                    'I': ci_state.get('I', 0),
                    'C_continuous': ci_state.get('C_continuous', ci_state.get('C', 0)),
                    'I_continuous': ci_state.get('I_continuous', ci_state.get('I', 0)),
                }
                level1_result = {'I_mean': ci_state.get('I', 0.5)}
                
                guide = self.l2_router.generate_orchestrator_guide(
                    query=query,
                    current_zone=zone,
                    level0_result=level0_result,
                    level1_result=level1_result
                )
                
                # Add metadata
                guide['_meta'] = {
                    'source': 'level2_light',
                    'latency_ms': (time.time() - start_time) * 1000,
                    'zone': zone
                }
                return guide
                
            except Exception as e:
                # Fall back to default guide
                pass
        
        # Default guide based on zone
        return self._generate_default_guide(zone, query, ci_state)
    
    def _generate_default_guide(self, zone: str, query: str, ci_state: Dict) -> Dict:
        """Generate default guide when L2 is unavailable"""
        
        guides = {
            'A': {
                'missing_info': [],
                'decomposable': True,
                'recommended': ['decompose_by_aspect', 'decompose_by_step'],
                'sub_problem_hints': ['Break down into logical components'],
                'confidence': 0.7,
                'validates_classification': True,
                '_meta': {'source': 'default', 'zone': 'A'}
            },
            'B': {
                'missing_info': ['additional_context'],
                'decomposable': True,
                'recommended': ['retrieve_first', 'decompose'],
                'sub_problem_hints': ['Check what information is missing'],
                'confidence': 0.6,
                'validates_classification': True,
                '_meta': {'source': 'default', 'zone': 'B'}
            },
            'C': {
                'missing_info': [],
                'decomposable': False,
                'recommended': ['direct_answer'],
                'sub_problem_hints': [],
                'confidence': 0.8,
                'validates_classification': True,
                '_meta': {'source': 'default', 'zone': 'C'}
            },
            'D': {
                'missing_info': ['relevant_documents', 'context'],
                'decomposable': False,
                'recommended': ['expand_retrieval', 'hybrid_search'],
                'sub_problem_hints': ['Find relevant information first'],
                'confidence': 0.6,
                'validates_classification': True,
                '_meta': {'source': 'default', 'zone': 'D'}
            }
        }
        
        return guides.get(zone, guides['C'])