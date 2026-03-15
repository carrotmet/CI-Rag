"""12-dimensional feature extraction for Level 0 classifier.

Target: <0.5ms feature extraction on modern CPU.
"""

import re
import math
from typing import Dict, List, Set, Optional
from collections import Counter
import numpy as np


class FeatureExtractor:
    """Extract 12-dimensional feature vector from query text."""
    
    # Domain keywords for domain_switch_cnt calculation
    DOMAIN_KEYWORDS: Dict[str, Set[str]] = {
        'medicine': {'医药', '医疗', '药品', '临床', '诊断', '医院', '医生', '患者', '治疗', '药物'},
        'technology': {'Kubernetes', 'Docker', '云原生', 'API', '算法', '代码', '编程', '系统', 
                      '服务器', '数据库', '人工智能', '机器学习', '深度学习'},
        'legal': {'合规', '法规', '法律', '合同', '条款', '诉讼', '知识产权', '隐私', '安全'},
        'finance': {'财务', '投资', '股票', '收益率', '成本', '利润', '预算', '会计', '资产'},
        'education': {'教育', '学习', '课程', '考试', '培训', '学校', '学生', '教师'},
        'business': {'公司', '企业', '管理', '运营', '战略', '市场', '销售', '客户'},
    }
    
    # Question indicators
    QUESTION_PARTICLES: Set[str] = {'吗', '什么', '怎么', '为什么', '多少', '哪里', '谁', '如何'}
    QUESTION_WORDS: Set[str] = {'how', 'what', 'why', 'when', 'where', 'who', 'which'}
    
    def __init__(self):
        self._pattern_question_cn = re.compile(r'[吗什么怎么为什么多少哪里谁如何]')
        self._pattern_question_en = re.compile(r'\?')
    
    def extract(self, query: str, user_history: Optional[Dict] = None) -> np.ndarray:
        """
        Extract 12-dimensional feature vector.
        
        Args:
            query: Input query string
            user_history: Optional user historical frequency data
            
        Returns:
            12-dimensional numpy array
        """
        features = np.zeros(12, dtype=np.float32)
        
        # 0. len_char: Character length
        features[0] = len(query)
        
        # 1. len_word: Word count (whitespace split)
        words = query.split()
        features[1] = len(words)
        
        # 2. char_entropy: Character-level Shannon entropy
        features[2] = self._compute_entropy(query)
        
        # 3. word_entropy: Word-level Shannon entropy
        features[3] = self._compute_entropy(words) if words else 0.0
        
        # 4. domain_switch_cnt: Domain transition count
        features[4] = self._count_domain_switches(query)
        
        # 5. has_question: Question indicator (0 or 1)
        features[5] = 1.0 if self._has_question(query) else 0.0
        
        # 6. digit_ratio: Proportion of digits
        features[6] = sum(c.isdigit() for c in query) / max(len(query), 1)
        
        # 7-11. user_historical_freq and other context features
        # For now, use placeholder values (to be implemented with actual user tracking)
        features[7] = user_history.get('query_freq', 0.5) if user_history else 0.5
        features[8] = user_history.get('avg_complexity', 0.5) if user_history else 0.5
        features[9] = user_history.get('success_rate', 0.5) if user_history else 0.5
        features[10] = 0.0  # Reserved for future use
        features[11] = 0.0  # Reserved for future use
        
        return features
    
    def _compute_entropy(self, data) -> float:
        """Compute Shannon entropy.
        
        For string: character-level entropy
        For list: element-level entropy
        """
        if isinstance(data, str):
            if len(data) == 0:
                return 0.0
            counter = Counter(data)
            length = len(data)
        elif isinstance(data, (list, tuple)):
            if len(data) == 0:
                return 0.0
            counter = Counter(data)
            length = len(data)
        else:
            return 0.0
        
        entropy = 0.0
        for count in counter.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy
    
    def _count_domain_switches(self, query: str) -> int:
        """Count domain transitions in query.
        
        Returns number of switches between different semantic domains.
        """
        query_lower = query.lower()
        detected_domains = []
        
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    detected_domains.append(domain)
                    break
        
        # Count switches (transitions between different domains)
        if len(detected_domains) <= 1:
            return 0
        
        switches = 0
        for i in range(1, len(detected_domains)):
            if detected_domains[i] != detected_domains[i-1]:
                switches += 1
        
        return min(switches, 5)  # Cap at 5 to prevent extreme values
    
    def _has_question(self, query: str) -> bool:
        """Detect if query is a question."""
        query_lower = query.lower()
        
        # Check Chinese question particles
        if self._pattern_question_cn.search(query):
            return True
        
        # Check English question words
        if any(word in query_lower for word in self.QUESTION_WORDS):
            return True
        
        # Check question mark
        if '?' in query or '？' in query:
            return True
        
        return False


# Convenience function
def extract_features(query: str, user_history: Optional[Dict] = None) -> np.ndarray:
    """Extract features from query."""
    extractor = FeatureExtractor()
    return extractor.extract(query, user_history)
