"""Centralized configuration for CI-RAG-ROUTER."""

from typing import List, Dict
from pydantic import Field
from pydantic_settings import BaseSettings
import os


class Level0Config(BaseSettings):
    """Level 0 configuration."""
    
    # Model paths
    model_c_path: str = Field(default="models/xgb_c.json", description="Complexity model path")
    model_i_path: str = Field(default="models/xgb_i.json", description="Information sufficiency model path")
    
    # Thresholds
    alpha: float = Field(default=0.7, description="Universal escape threshold")
    cold_start_alpha: float = Field(default=0.6, description="Conservative threshold during initial training phase")
    
    # XGBoost parameters
    xgb_max_depth: int = 6
    xgb_n_estimators: int = 150
    xgb_learning_rate: float = 0.05
    xgb_subsample: float = 0.8
    xgb_colsample_bytree: float = 0.8
    
    # Heuristic parameters
    domain_keywords: Dict[str, List[str]] = Field(default_factory=lambda: {
        'medicine': ['医药', '医疗', '药品', '临床', '诊断', '医院', '医生', '患者'],
        'technology': ['Kubernetes', 'Docker', '云原生', 'API', '算法', '代码', '编程', '系统'],
        'legal': ['合规', '法规', '法律', '合同', '条款', '诉讼', '知识产权'],
        'finance': ['财务', '投资', '股票', '收益率', '成本', '利润', '预算', '会计'],
        'education': ['教育', '学习', '课程', '考试', '培训', '学校'],
    })
    
    # Feature thresholds for heuristic
    high_complexity_word_threshold: int = 50
    high_complexity_domain_switch: int = 2
    high_entropy_threshold: float = 4.0
    simple_query_word_threshold: int = 10


class CIConfig(BaseSettings):
    """Global CI-RAG-ROUTER configuration."""
    
    # Level 0
    level0: Level0Config = Field(default_factory=Level0Config)
    
    # Debug
    debug: bool = Field(default=False, env="CI_DEBUG")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global config instance
config = CIConfig()
