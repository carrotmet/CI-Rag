"""
Zone A Handler - Decomposition Zone (C=1, I=1)

V4 Architecture:
- Guide checks/generates internally
- Executes one round of decomposition
- Requests orchestrator for transition
- Handles strategy upgrade on rejection
"""

from typing import Dict, List, Optional, Any
from .base import ZoneHandler, ZoneResult, ZoneType


class ZoneAHandler(ZoneHandler):
    """
    Zone A: Complex + Well-covered (C=1, I=1)
    
    Responsibility:
    - Decompose complex problems into sub-problems
    - Each sub-problem should have C=0 (simple)
    - Request orchestrator to route sub-problems to Zone C
    """
    
    def __init__(self, guide_generator=None, strategy_manager=None, 
                 llm_client=None, retrieval_engine=None):
        super().__init__(ZoneType.A, guide_generator, strategy_manager)
        self.llm_client = llm_client
        self.retrieval_engine = retrieval_engine
        
    def execute_round(self, query: str, guide: Optional[Dict], context: Dict) -> ZoneResult:
        """
        Execute one round of decomposition.
        
        Args:
            query: The query to decompose
            guide: Orchestrator guide with decomposition hints
            context: Processing context (round number, etc.)
            
        Returns:
            ZoneResult with sub-problems
        """
        round_number = context.get('round_number', 1)
        strategy = context.get('strategy', 'decompose_by_aspect')
        
        # Get decomposition strategy from guide or use default
        if guide and 'recommended' in guide:
            strategy = guide['recommended'][0] if guide['recommended'] else strategy
        
        # Perform decomposition
        sub_problems = self._decompose(query, guide, strategy)
        
        # Assess CI for each sub-problem
        sub_problems_with_ci = []
        all_simple = True
        
        for sp in sub_problems:
            # Assess if this sub-problem is simple (C=0)
            ci = self._assess_subproblem_ci(sp['query'])
            sp['ci_state'] = ci
            sp['is_simple'] = ci['C'] == 0
            
            if not sp['is_simple']:
                all_simple = False
                
            sub_problems_with_ci.append(sp)
        
        # Update CI state - all sub-problems should be C=0
        # If not, we need more decomposition (handled by strategy upgrade)
        new_ci = {
            'C': 0 if all_simple else 1,  # C=0 means ready for Zone C
            'I': 1,  # Information is sufficient (we decomposed with full context)
            'C_continuous': 0.0 if all_simple else 0.6,
            'I_continuous': 0.9,
            'sigma_c': 0.7,
            'sigma_i': 0.8,
            'sigma_joint': 0.7
        }
        
        return ZoneResult(
            success=True,
            zone=self.zone_type,
            query=query,
            ci_state=new_ci,
            output=None,  # No direct output, sub-problems will be processed
            sub_problems=sub_problems_with_ci,
            strategy_used=strategy,
            round_number=round_number,
            metadata={
                'decomposition_count': len(sub_problems),
                'all_simple': all_simple,
                'guide_used': guide is not None
            }
        )
    
    def _decompose(self, query: str, guide: Optional[Dict], strategy: str) -> List[Dict]:
        """
        Decompose query into sub-problems.
        
        Args:
            query: Original query
            guide: Decomposition guide
            strategy: Decomposition strategy
            
        Returns:
            List of sub-problem dicts
        """
        # If LLM client available, use it for decomposition
        if self.llm_client:
            return self._llm_decompose(query, guide, strategy)
        
        # Fallback: simple rule-based decomposition
        return self._rule_based_decompose(query, guide, strategy)
    
    def _llm_decompose(self, query: str, guide: Optional[Dict], strategy: str) -> List[Dict]:
        """Use LLM for intelligent decomposition"""
        hints = guide.get('sub_problem_hints', []) if guide else []
        
        prompt = f"""Decompose the following complex query into 2-4 simple sub-problems.
Each sub-problem should be answerable independently.

Query: {query}

Strategy: {strategy}
Hints: {', '.join(hints) if hints else 'None'}

Provide output as numbered list:
1. [Sub-problem 1]
2. [Sub-problem 2]
..."""

        try:
            response = self.llm_client.complete(prompt)
            # Parse numbered list
            lines = [l.strip() for l in response.split('\n') if l.strip()]
            sub_problems = []
            
            for i, line in enumerate(lines):
                # Remove numbering (1., 1), etc.)
                text = line
                for prefix in [f"{j}." for j in range(1, 10)] + [f"{j})" for j in range(1, 10)]:
                    if text.startswith(prefix):
                        text = text[len(prefix):].strip()
                        break
                
                if text and len(text) > 10:
                    sub_problems.append({
                        'id': f"sp_{i+1}",
                        'query': text,
                        'parent_query': query
                    })
            
            return sub_problems
        except Exception:
            return self._rule_based_decompose(query, guide, strategy)
    
    def _rule_based_decompose(self, query: str, guide: Optional[Dict], strategy: str) -> List[Dict]:
        """Simple rule-based decomposition as fallback"""
        # Split by common conjunctions
        import re
        
        # Simple heuristics for decomposition
        parts = re.split(r'[，。；？！,;?!]', query)
        parts = [p.strip() for p in parts if len(p.strip()) > 5]
        
        if len(parts) <= 1:
            # Create aspect-based sub-problems
            return [
                {'id': 'sp_1', 'query': f'分析{query}的背景和原因', 'parent_query': query},
                {'id': 'sp_2', 'query': f'解释{query}的具体内容', 'parent_query': query},
                {'id': 'sp_3', 'query': f'总结{query}的影响和结论', 'parent_query': query}
            ]
        
        return [
            {'id': f'sp_{i+1}', 'query': p, 'parent_query': query}
            for i, p in enumerate(parts[:4])  # Max 4 sub-problems
        ]
    
    def _assess_subproblem_ci(self, query: str) -> Dict:
        """
        Assess CI for a sub-problem.
        Simple heuristic: short queries are likely C=0 (simple)
        """
        length = len(query)
        
        # Simple heuristic
        is_simple = length < 50 or ('什么' in query and length < 80)
        
        return {
            'C': 0 if is_simple else 1,
            'I': 1,  # Assume information sufficient after decomposition
            'C_continuous': 0.3 if is_simple else 0.7,
            'I_continuous': 0.9
        }
    
    def can_self_transition(self, ci_state: Dict) -> bool:
        """
        Zone A can self-transition if a sub-problem is still complex.
        It will re-decompose without involving orchestrator.
        """
        # If we have sub-problems that are still complex, we can re-decompose
        return True