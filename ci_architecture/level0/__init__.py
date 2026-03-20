"""Level 0: Zero-Token XGBoost Classifier with Heuristic Fallback."""

from .features import FeatureExtractor, extract_features
from .heuristic_router import HeuristicRouter
from .classifier import XGBoostClassifier
from .router import Level0Router, RouterStatus, route_query

# Optional: cntext-enhanced feature extractor
try:
    from .features_cntext import CntextFeatureExtractor
    __all__ = [
        "FeatureExtractor",
        "extract_features",
        "HeuristicRouter",
        "XGBoostClassifier",
        "Level0Router",
        "RouterStatus",
        "route_query",
        "CntextFeatureExtractor",
    ]
except ImportError:
    __all__ = [
        "FeatureExtractor",
        "extract_features",
        "HeuristicRouter",
        "XGBoostClassifier",
        "Level0Router",
        "RouterStatus",
        "route_query",
    ]
