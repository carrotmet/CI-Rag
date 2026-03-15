"""XGBoost dual classifier for Level 0.

Implements Model C (Complexity) and Model I (Information Sufficiency).
Target: <1ms end-to-end inference on modern CPU.
"""

import os
import pickle
from typing import Dict, Optional, Tuple
import numpy as np

# Optional import - handle gracefully if xgboost not installed
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    xgb = None


class XGBoostClassifier:
    """
    Dual XGBoost classifier for Complexity (C) and Information Sufficiency (I).
    """
    
    def __init__(self, 
                 model_c_path: Optional[str] = None,
                 model_i_path: Optional[str] = None,
                 alpha: float = 0.7):
        """
        Initialize classifier.
        
        Args:
            model_c_path: Path to complexity model file
            model_i_path: Path to information sufficiency model file
            alpha: Escape threshold
        """
        if not XGBOOST_AVAILABLE:
            raise ImportError("xgboost is required. Install with: pip install xgboost>=2.0.0")
        
        self.model_c: Optional[xgb.Booster] = None
        self.model_i: Optional[xgb.Booster] = None
        self.alpha = alpha
        self._is_loaded = False
        
        if model_c_path and model_i_path:
            self.load_models(model_c_path, model_i_path)
    
    def load_models(self, model_c_path: str, model_i_path: str) -> bool:
        """
        Load XGBoost models from disk.
        
        Returns:
            True if both models loaded successfully
        """
        if not XGBOOST_AVAILABLE:
            return False
        
        try:
            if os.path.exists(model_c_path):
                self.model_c = xgb.Booster()
                self.model_c.load_model(model_c_path)
                # Verify model is not empty
                if len(self.model_c.get_dump()) == 0:
                    self.model_c = None
            
            if os.path.exists(model_i_path):
                self.model_i = xgb.Booster()
                self.model_i.load_model(model_i_path)
                if len(self.model_i.get_dump()) == 0:
                    self.model_i = None
            
            self._is_loaded = (self.model_c is not None and self.model_i is not None)
            return self._is_loaded
            
        except Exception as e:
            print(f"Error loading models: {e}")
            self.model_c = None
            self.model_i = None
            self._is_loaded = False
            return False
    
    def is_loaded(self) -> bool:
        """Check if both models are loaded and valid."""
        return self._is_loaded
    
    def predict(self, features: np.ndarray) -> Dict:
        """
        Execute dual inference with conservative confidence aggregation.
        
        Args:
            features: 12-dimensional feature vector
            
        Returns:
            Dict with C, I, confidence scores, and escalation decision
        """
        if not self._is_loaded:
            raise RuntimeError("Models not loaded. Call load_models() first.")
        
        # Ensure 2D array
        if features.ndim == 1:
            features = features.reshape(1, -1)
        
        # Create DMatrix
        dmatrix = xgb.DMatrix(features)
        
        # Probability extraction
        proba_c = self.model_c.predict(dmatrix)
        proba_i = self.model_i.predict(dmatrix)
        
        # Handle output format (XGBoost may return 1D for binary)
        if proba_c.ndim == 1:
            proba_c = np.column_stack([1 - proba_c, proba_c])
        if proba_i.ndim == 1:
            proba_i = np.column_stack([1 - proba_i, proba_i])
        
        # Discrete hard decisions (threshold = 0.5)
        C = 1 if proba_c[0, 1] > 0.5 else 0
        I = 1 if proba_i[0, 1] > 0.5 else 0
        
        # Conservative confidence: take max probability for predicted class
        sigma_c = float(np.max(proba_c[0]))
        sigma_i = float(np.max(proba_i[0]))
        
        # Joint confidence: pessimistic aggregation
        sigma_joint = min(sigma_c, sigma_i)
        
        return {
            'C_discrete': C,
            'I_discrete': I,
            'C_continuous': float(proba_c[0, 1]),
            'I_continuous': float(proba_i[0, 1]),
            'sigma_c': sigma_c,
            'sigma_i': sigma_i,
            'sigma_joint': sigma_joint,
            'escalate': sigma_joint < self.alpha,
            'mode': 'XGBOOST'
        }
    
    @staticmethod
    def train(X_train: np.ndarray, 
              y_c_train: np.ndarray,
              y_i_train: np.ndarray,
              X_val: Optional[np.ndarray] = None,
              y_c_val: Optional[np.ndarray] = None,
              y_i_val: Optional[np.ndarray] = None,
              output_dir: str = "models") -> Tuple[bool, str]:
        """
        Train dual XGBoost classifiers.
        
        Args:
            X_train: Training features
            y_c_train: Training labels for complexity
            y_i_train: Training labels for information sufficiency
            X_val: Validation features
            y_c_val: Validation labels for complexity
            y_i_val: Validation labels for information sufficiency
            output_dir: Directory to save models
            
        Returns:
            (success, message)
        """
        if not XGBOOST_AVAILABLE:
            return False, "xgboost not installed"
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # Model C: Complexity
            print("Training Model C (Complexity)...")
            dtrain_c = xgb.DMatrix(X_train, label=y_c_train)
            
            params_c = {
                'max_depth': 6,
                'eta': 0.05,
                'objective': 'binary:logistic',
                'eval_metric': 'logloss',
                'tree_method': 'hist',
                'subsample': 0.8,
                'colsample_bytree': 0.8,
            }
            
            if X_val is not None and y_c_val is not None:
                dval_c = xgb.DMatrix(X_val, label=y_c_val)
                model_c = xgb.train(
                    params_c,
                    dtrain_c,
                    num_boost_round=150,
                    evals=[(dval_c, 'validation')],
                    early_stopping_rounds=20,
                    verbose_eval=False
                )
            else:
                model_c = xgb.train(params_c, dtrain_c, num_boost_round=150)
            
            # Model I: Information Sufficiency
            print("Training Model I (Information Sufficiency)...")
            dtrain_i = xgb.DMatrix(X_train, label=y_i_train)
            
            params_i = {
                'max_depth': 6,
                'eta': 0.05,
                'objective': 'binary:logistic',
                'eval_metric': 'logloss',
                'tree_method': 'hist',
                'subsample': 0.8,
                'colsample_bytree': 0.8,
            }
            
            if X_val is not None and y_i_val is not None:
                dval_i = xgb.DMatrix(X_val, label=y_i_val)
                model_i = xgb.train(
                    params_i,
                    dtrain_i,
                    num_boost_round=150,
                    evals=[(dval_i, 'validation')],
                    early_stopping_rounds=20,
                    verbose_eval=False
                )
            else:
                model_i = xgb.train(params_i, dtrain_i, num_boost_round=150)
            
            # Save models
            model_c.save_model(f"{output_dir}/xgb_c.json")
            model_i.save_model(f"{output_dir}/xgb_i.json")
            
            return True, f"Models saved to {output_dir}"
            
        except Exception as e:
            return False, f"Training failed: {str(e)}"
