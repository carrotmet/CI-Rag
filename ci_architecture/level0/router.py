"""Unified Level 0 Router with cold start support.

Architecture: Heuristic rules + XGBoost parallel
- Before XGBoost training: Heuristic only, force escalation to Level 1
- After XGBoost training: Parallel execution, XGBoost priority, heuristic fallback
"""

import os
from enum import Enum
from typing import Dict, Optional
import numpy as np

from ..config import config
from .features import FeatureExtractor
from .heuristic_router import HeuristicRouter
from .classifier import XGBoostClassifier


class RouterStatus(str, Enum):
    """Router operational status."""
    COLD_START = "COLD_START"      # XGBoost not available, heuristic only
    INITIAL = "INITIAL"            # XGBoost available, conservative threshold
    CALIBRATED = "CALIBRATED"      # XGBoost with calibration
    PRODUCTION = "PRODUCTION"      # Fully operational


class Level0Router:
    """
    Unified Level 0 Router.
    
    Implements dual-track architecture:
    1. Check model state
    2. If not trained -> Heuristic only (cold start)
    3. If trained -> XGBoost + Heuristic parallel, XGBoost priority
    """
    
    def __init__(self, 
                 model_c_path: Optional[str] = None,
                 model_i_path: Optional[str] = None,
                 alpha: Optional[float] = None):
        """
        Initialize router.
        
        Args:
            model_c_path: Path to complexity model (defaults to config)
            model_i_path: Path to information sufficiency model (defaults to config)
            alpha: Escape threshold (defaults to config)
        """
        self.config = config.level0
        self.model_c_path = model_c_path or self.config.model_c_path
        self.model_i_path = model_i_path or self.config.model_i_path
        self.alpha = alpha or self.config.alpha
        
        # Initialize components
        self.feature_extractor = FeatureExtractor()
        self.heuristic = HeuristicRouter()
        self.xgb: Optional[XGBoostClassifier] = None
        
        # Detect model state and initialize accordingly
        self._detect_and_initialize()
    
    def _detect_and_initialize(self) -> None:
        """Detect model state and initialize XGBoost if available."""
        if self._check_model_valid(self.model_c_path) and \
           self._check_model_valid(self.model_i_path):
            try:
                self.xgb = XGBoostClassifier(
                    model_c_path=self.model_c_path,
                    model_i_path=self.model_i_path,
                    alpha=self.alpha
                )
                if self.xgb.is_loaded():
                    self.status = RouterStatus.PRODUCTION
                else:
                    self.status = RouterStatus.COLD_START
                    self.xgb = None
            except Exception as e:
                print(f"Warning: Failed to load XGBoost models: {e}")
                self.status = RouterStatus.COLD_START
                self.xgb = None
        else:
            self.status = RouterStatus.COLD_START
            print(f"Info: XGBoost models not found or invalid. Running in COLD_START mode.")
            print(f"      Model paths: {self.model_c_path}, {self.model_i_path}")
    
    def _check_model_valid(self, path: str) -> bool:
        """
        Check if model file exists and is valid.
        
        Returns:
            True if model file exists, can be loaded, and has content
        """
        if not os.path.exists(path):
            return False
        
        try:
            # Try to load and validate
            import xgboost as xgb
            model = xgb.Booster()
            model.load_model(path)
            # Check if model has trees (non-empty)
            return len(model.get_dump()) > 0
        except Exception:
            return False
    
    def get_status(self) -> RouterStatus:
        """Get current router status."""
        return self.status
    
    def is_cold_start(self) -> bool:
        """Check if router is in cold start mode."""
        return self.status == RouterStatus.COLD_START
    
    def route(self, query: str, user_history: Optional[Dict] = None) -> Dict:
        """
        Route query through Level 0.
        
        Args:
            query: Input query string
            user_history: Optional user historical data
            
        Returns:
            Routing decision with CI values, confidence, and escalation flag
        """
        # Extract features
        features = self.feature_extractor.extract(query, user_history)
        
        # Route based on current status
        if self.status == RouterStatus.COLD_START:
            return self._route_cold_start(features)
        else:
            return self._route_parallel(features)
    
    def _route_cold_start(self, features: np.ndarray) -> Dict:
        """
        Cold start routing: heuristic only, force escalation.
        
        All queries are marked as uncertain to force Level 1 data collection.
        """
        heuristic_result = self.heuristic.predict(features)
        
        # Force low confidence to ensure escalation to Level 1
        # This allows us to collect training data from Level 1/2
        return {
            'C': heuristic_result['C'],
            'I': heuristic_result['I'],
            'C_continuous': float(heuristic_result['C']),
            'I_continuous': float(heuristic_result['I']),
            'sigma_c': 0.5,  # Force low confidence
            'sigma_i': 0.5,  # Force low confidence
            'sigma_joint': 0.5,  # < 0.7, triggers escalation
            'escalate': True,
            'status': self.status.value,
            'mode': 'COLD_START_HEURISTIC',
            'note': 'XGBoost models not trained. Escalating to Level 1 for data collection.',
            'features': features.tolist()
        }
    
    def _route_parallel(self, features: np.ndarray) -> Dict:
        """
        Parallel routing: XGBoost + Heuristic.
        
        Priority: XGBoost high confidence -> use XGBoost
                  XGBoost low confidence -> fallback to heuristic
        """
        # Get XGBoost prediction
        xgb_result = self.xgb.predict(features)
        
        # Get heuristic prediction as backup
        heuristic_result = self.heuristic.predict(features)
        
        # Decision logic
        if xgb_result['sigma_joint'] >= self.alpha:
            # XGBoost confident - use it
            return {
                'C': xgb_result['C_discrete'],
                'I': xgb_result['I_discrete'],
                'C_continuous': xgb_result['C_continuous'],
                'I_continuous': xgb_result['I_continuous'],
                'sigma_c': xgb_result['sigma_c'],
                'sigma_i': xgb_result['sigma_i'],
                'sigma_joint': xgb_result['sigma_joint'],
                'escalate': False,
                'status': self.status.value,
                'mode': 'XGBOOST_HIGH_CONF',
                'heuristic_backup': {
                    'C': heuristic_result['C'],
                    'I': heuristic_result['I']
                },
                'features': features.tolist()
            }
        else:
            # XGBoost not confident - check if heuristic has stronger opinion
            # For now, we still escalate but include both results for analysis
            return {
                'C': xgb_result['C_discrete'],
                'I': xgb_result['I_discrete'],
                'C_continuous': xgb_result['C_continuous'],
                'I_continuous': xgb_result['I_continuous'],
                'sigma_c': xgb_result['sigma_c'],
                'sigma_i': xgb_result['sigma_i'],
                'sigma_joint': xgb_result['sigma_joint'],
                'escalate': True,
                'status': self.status.value,
                'mode': 'XGBOOST_LOW_CONF_ESCALATE',
                'heuristic_backup': {
                    'C': heuristic_result['C'],
                    'I': heuristic_result['I']
                },
                'features': features.tolist()
            }
    
    def reload_models(self) -> bool:
        """
        Reload models (useful for hot-swapping or after training).
        
        Returns:
            True if models loaded successfully
        """
        self._detect_and_initialize()
        return self.status != RouterStatus.COLD_START
    
    def get_zone(self, C: int, I: int) -> str:
        """
        Map C and I to ABCD zone.
        
        Returns:
            Zone letter: 'A', 'B', 'C', or 'D'
        """
        zone_map = {(0, 0): 'D', (0, 1): 'C', (1, 0): 'B', (1, 1): 'A'}
        return zone_map.get((C, I), 'B')  # Default to B (conservative)


# Convenience function for direct usage
def route_query(query: str, 
                model_c_path: Optional[str] = None,
                model_i_path: Optional[str] = None) -> Dict:
    """
    Route a single query through Level 0.
    
    Args:
        query: Input query string
        model_c_path: Optional path to complexity model
        model_i_path: Optional path to information sufficiency model
        
    Returns:
        Routing decision
    """
    router = Level0Router(model_c_path, model_i_path)
    return router.route(query)
