"""
Sub-problem Message Queue for V4 architecture.

Used by Zone C to collect sub-problem results and assemble final output.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import time
import uuid


@dataclass
class SubProblemResult:
    """Result from a sub-problem processing"""
    subproblem_id: str
    parent_id: str
    query: str
    answer: str
    ci_state: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class SubProblemQueue:
    """
    Message queue for sub-problem result collection.
    
    V4 Architecture:
    - Zone A decomposes parent problem into sub-problems
    - Each sub-problem is processed and result put in queue
    - Zone C collects all results and assembles final output
    """
    
    def __init__(self):
        # parent_id -> list of SubProblemResult
        self._results: Dict[str, List[SubProblemResult]] = defaultdict(list)
        # parent_id -> expected sub-problem count
        self._expected_counts: Dict[str, int] = {}
        # parent_id -> metadata
        self._metadata: Dict[str, Dict] = {}
        
    def register_parent(self, parent_id: str, subproblem_ids: List[str], 
                       metadata: Dict = None):
        """
        Register a parent problem with its sub-problems.
        
        Args:
            parent_id: Parent problem ID
            subproblem_ids: List of expected sub-problem IDs
            metadata: Additional metadata for this parent
        """
        self._expected_counts[parent_id] = len(subproblem_ids)
        self._metadata[parent_id] = metadata or {}
        self._metadata[parent_id]['subproblem_ids'] = subproblem_ids
        self._metadata[parent_id]['registered_at'] = time.time()
    
    def put(self, result: SubProblemResult) -> bool:
        """
        Put a sub-problem result into the queue.
        
        Args:
            result: SubProblemResult to store
            
        Returns:
            True if this was the last result needed
        """
        parent_id = result.parent_id
        self._results[parent_id].append(result)
        
        return self.is_complete(parent_id)
    
    def put_simple(self, parent_id: str, subproblem_id: str, 
                  query: str, answer: str, ci_state: Dict = None):
        """
        Simplified put method.
        
        Args:
            parent_id: Parent problem ID
            subproblem_id: Sub-problem ID
            query: Sub-problem query
            answer: Sub-problem answer
            ci_state: CI state dict
        """
        result = SubProblemResult(
            subproblem_id=subproblem_id,
            parent_id=parent_id,
            query=query,
            answer=answer,
            ci_state=ci_state or {}
        )
        return self.put(result)
    
    def is_complete(self, parent_id: str) -> bool:
        """
        Check if all sub-problems are complete for a parent.
        
        Args:
            parent_id: Parent problem ID
            
        Returns:
            True if all sub-problems have results
        """
        if parent_id not in self._expected_counts:
            return False
        
        completed = len(self._results[parent_id])
        expected = self._expected_counts[parent_id]
        return completed >= expected
    
    def get_all(self, parent_id: str) -> List[SubProblemResult]:
        """
        Get all sub-problem results for a parent.
        
        Args:
            parent_id: Parent problem ID
            
        Returns:
            List of SubProblemResult
        """
        return self._results.get(parent_id, [])
    
    def get_progress(self, parent_id: str) -> Dict:
        """
        Get completion progress for a parent.
        
        Args:
            parent_id: Parent problem ID
            
        Returns:
            Dict with completed, expected, percentage
        """
        completed = len(self._results.get(parent_id, []))
        expected = self._expected_counts.get(parent_id, 0)
        percentage = (completed / expected * 100) if expected > 0 else 0
        
        return {
            'parent_id': parent_id,
            'completed': completed,
            'expected': expected,
            'percentage': round(percentage, 1),
            'is_complete': completed >= expected
        }
    
    def get_pending(self, parent_id: str) -> List[str]:
        """
        Get list of pending (incomplete) sub-problem IDs.
        
        Args:
            parent_id: Parent problem ID
            
        Returns:
            List of pending sub-problem IDs
        """
        if parent_id not in self._metadata:
            return []
        
        all_ids = set(self._metadata[parent_id].get('subproblem_ids', []))
        completed_ids = set(r.subproblem_id for r in self._results.get(parent_id, []))
        
        return list(all_ids - completed_ids)
    
    def cleanup(self, max_age_seconds: float = 3600):
        """
        Clean up old entries.
        
        Args:
            max_age_seconds: Maximum age of entries to keep
        """
        current_time = time.time()
        to_remove = []
        
        for parent_id, metadata in self._metadata.items():
            registered_at = metadata.get('registered_at', 0)
            if current_time - registered_at > max_age_seconds:
                to_remove.append(parent_id)
        
        for parent_id in to_remove:
            del self._results[parent_id]
            del self._expected_counts[parent_id]
            del self._metadata[parent_id]