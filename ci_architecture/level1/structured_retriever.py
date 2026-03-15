"""Structured Data Retrieval (Intent Recognition + Schema Matching).

For medical domain: Maps symptom queries to structured disease criteria.
Target latency: 10-30ms
"""

import re
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict


class StructuredIntent(Enum):
    """Structured query intent types."""
    SYMPTOM_LOOKUP = auto()      # "What disease has symptom X?"
    DIAGNOSIS_CRITERIA = auto()  # "Diagnostic criteria for X"
    COMPARISON = auto()          # "Compare X and Y"
    TREATMENT_QUERY = auto()     # "Treatment for X"
    UNSUPPORTED = auto()         # No structured mapping


@dataclass
class IntentResult:
    """Intent recognition result."""
    intent: StructuredIntent
    confidence: float
    entities: Dict[str, any]
    matched_patterns: List[str]
    missing_slots: List[str]


@dataclass
class StructuredResult:
    """Structured retrieval result."""
    schema_match_rate: float
    row_count: int
    null_ratio: float
    success: bool
    results: List[Dict]
    error: Optional[str] = None


class IntentRecognizer:
    """
    Rule-based intent recognition for medical queries.
    
    Recognizes query patterns and extracts entities for structured lookup.
    """
    
    # Medical domain patterns
    PATTERNS = {
        StructuredIntent.SYMPTOM_LOOKUP: [
            r'(?:什么|哪些)病.*?(?:症状|表现).*?(\w+)',
            r'(\w+).*?(?:症状|表现).*?(?:什么|哪些)病',
            r'(?:有|出现)(\w+).*?(?:是|可能)(\w+)',
            r'(咳嗽|发热|胸痛|头痛|腹泻).*?(?:什么|哪种)',
        ],
        StructuredIntent.DIAGNOSIS_CRITERIA: [
            r'(\w+).*?(?:诊断标准|诊断依据|如何诊断)',
            r'(?:怎样|如何).*?(?:确诊|诊断)(\w+)',
            r'(\w+).*?(?:需要|要做).*?(?:检查|检验)',
        ],
        StructuredIntent.COMPARISON: [
            r'(\w+)和(\w+).*?(?:区别|差异|比较)',
            r'(?:比较|对比)(\w+)与(\w+)',
            r'(\w+)还是(\w+)',
        ],
        StructuredIntent.TREATMENT_QUERY: [
            r'(\w+).*?(?:治疗|用药|方案)',
            r'(?:怎么|如何).*?(?:治|治疗)(\w+)',
            r'(\w+).*?(?:吃|用).*?(?:药|什么)',
        ],
    }
    
    # Medical entity patterns
    ENTITY_PATTERNS = {
        'symptom': [
            r'(发热|咳嗽|咳痰|胸痛|呼吸困难|心悸|头痛|头晕|恶心|呕吐|腹痛|腹泻|黄疸|水肿|出血)',
            r'(哮鸣音|湿啰音|心脏杂音|肝大|脾大)',
        ],
        'disease': [
            r'(肺炎|哮喘|结核|冠心病|心梗|心绞痛|心力衰竭|胃炎|溃疡|肝硬化|肾炎|糖尿病|高血压)',
            r'(脑梗死|脑出血|癫痫|帕金森|红斑狼疮|类风湿)',
        ],
        'lab_test': [
            r'(血常规|尿常规|生化|心电图|CT|MRI|X线|超声|内镜)',
            r'(ST段|Q波|淀粉酶|肌钙蛋白|血糖|血红蛋白)',
        ],
        'body_part': [
            r'(心|肺|肝|肾|脑|胃|肠|胸|腹|头|四肢)',
        ],
    }
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns."""
        self.compiled_patterns = {}
        for intent, patterns in self.PATTERNS.items():
            self.compiled_patterns[intent] = [re.compile(p) for p in patterns]
        
        self.compiled_entities = {}
        for entity_type, patterns in self.ENTITY_PATTERNS.items():
            self.compiled_entities[entity_type] = [re.compile(p) for p in patterns]
    
    def recognize(self, query: str) -> IntentResult:
        """
        Recognize query intent.
        
        Args:
            query: Input query string
            
        Returns:
            IntentResult with recognized intent and entities
        """
        query_lower = query.lower()
        
        # Score each intent
        intent_scores = defaultdict(float)
        matched_patterns = defaultdict(list)
        
        for intent, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(query_lower)
                if matches:
                    # Higher score for longer matches
                    match_len = len(str(matches[0])) if matches else 0
                    score = 0.3 + 0.7 * min(match_len / len(query_lower), 1.0)
                    if score > intent_scores[intent]:
                        intent_scores[intent] = score
                        matched_patterns[intent] = [pattern.pattern]
        
        # Extract entities
        entities = self._extract_entities(query_lower)
        
        # Select primary intent
        if not intent_scores:
            primary_intent = StructuredIntent.UNSUPPORTED
            confidence = 0.9
        else:
            primary_intent = max(intent_scores, key=intent_scores.get)
            confidence = intent_scores[primary_intent]
        
        # Determine missing slots
        required_slots = self._get_required_slots(primary_intent)
        missing_slots = [s for s in required_slots if s not in entities]
        
        return IntentResult(
            intent=primary_intent,
            confidence=confidence,
            entities=entities,
            matched_patterns=matched_patterns.get(primary_intent, []),
            missing_slots=missing_slots
        )
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Extract medical entities from query."""
        entities = {}
        
        for entity_type, patterns in self.compiled_entities.items():
            found = set()
            for pattern in patterns:
                matches = pattern.findall(query)
                found.update(matches)
            if found:
                entities[entity_type] = list(found)
        
        # Extract numbers (lab values, etc.)
        numbers = re.findall(r'(\d+\.?\d*)\s*(mg|g|mmol|U/L|%)?', query)
        if numbers:
            entities['numbers'] = [n[0] for n in numbers]
        
        return entities
    
    def _get_required_slots(self, intent: StructuredIntent) -> List[str]:
        """Get required slots for intent."""
        required = {
            StructuredIntent.SYMPTOM_LOOKUP: ['symptom'],
            StructuredIntent.DIAGNOSIS_CRITERIA: ['disease'],
            StructuredIntent.COMPARISON: ['disease'],
            StructuredIntent.TREATMENT_QUERY: ['disease'],
        }
        return required.get(intent, [])


class StructuredRetriever:
    """
    Structured data retriever for medical knowledge base.
    
    Maps queries to structured disease information including:
    - Diagnostic criteria
    - Symptom-disease mappings
    - Treatment guidelines
    """
    
    def __init__(self, knowledge_base: List[Dict] = None):
        """
        Initialize structured retriever.
        
        Args:
            knowledge_base: List of disease records with structured fields
        """
        self.intent_recognizer = IntentRecognizer()
        self.knowledge_base = knowledge_base or []
        
        # Build indexes
        self._build_indexes()
    
    def _build_indexes(self):
        """Build indexes for efficient lookup."""
        # Disease name index
        self.disease_index = {}
        # Symptom index
        self.symptom_index = defaultdict(set)
        # Category index
        self.category_index = defaultdict(set)
        
        for i, record in enumerate(self.knowledge_base):
            meta = record.get('metadata', {})
            
            # Index by disease name
            disease = meta.get('disease', '')
            if disease:
                self.disease_index[disease] = i
            
            # Index by symptoms
            symptoms = meta.get('key_symptoms', [])
            for symptom in symptoms:
                self.symptom_index[symptom].add(i)
            
            # Index by category
            category = meta.get('category', '')
            if category:
                self.category_index[category].add(i)
    
    def search(self, query: str) -> StructuredResult:
        """
        Execute structured search.
        
        Args:
            query: Query string
            
        Returns:
            StructuredResult with matches and schema match rate
        """
        # Recognize intent
        intent_result = self.intent_recognizer.recognize(query)
        
        # Execute based on intent
        if intent_result.intent == StructuredIntent.SYMPTOM_LOOKUP:
            return self._search_by_symptoms(intent_result)
        elif intent_result.intent == StructuredIntent.DIAGNOSIS_CRITERIA:
            return self._search_by_disease(intent_result)
        elif intent_result.intent == StructuredIntent.COMPARISON:
            return self._search_comparison(intent_result)
        else:
            # Generic search
            return self._search_generic(query, intent_result)
    
    def _search_by_symptoms(self, intent_result: IntentResult) -> StructuredResult:
        """Search diseases by symptoms."""
        symptoms = intent_result.entities.get('symptom', [])
        
        if not symptoms:
            return StructuredResult(
                schema_match_rate=0.0,
                row_count=0,
                null_ratio=1.0,
                success=False,
                results=[],
                error="No symptoms found"
            )
        
        # Find diseases matching symptoms
        candidate_scores = defaultdict(float)
        
        for symptom in symptoms:
            for doc_id in self.symptom_index.get(symptom, []):
                candidate_scores[doc_id] += 1.0
        
        # Sort by match count
        sorted_candidates = sorted(
            candidate_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Build results
        results = []
        for doc_id, score in sorted_candidates[:5]:
            record = self.knowledge_base[doc_id]
            results.append({
                'disease': record['metadata'].get('disease', ''),
                'category': record['metadata'].get('category', ''),
                'symptom_match': score,
                'content': record['content'][:200],
                'key_symptoms': record['metadata'].get('key_symptoms', [])
            })
        
        # Calculate metrics
        schema_match = len(symptoms) / max(len(intent_result.missing_slots) + len(symptoms), 1)
        
        return StructuredResult(
            schema_match_rate=schema_match,
            row_count=len(results),
            null_ratio=0.0 if results else 1.0,
            success=True,
            results=results
        )
    
    def _search_by_disease(self, intent_result: IntentResult) -> StructuredResult:
        """Search diagnostic criteria by disease name."""
        diseases = intent_result.entities.get('disease', [])
        
        results = []
        for disease in diseases:
            if disease in self.disease_index:
                doc_id = self.disease_index[disease]
                record = self.knowledge_base[doc_id]
                results.append({
                    'disease': disease,
                    'category': record['metadata'].get('category', ''),
                    'content': record['content'],
                    'key_symptoms': record['metadata'].get('key_symptoms', []),
                    'complexity': record['metadata'].get('complexity', 0.5)
                })
        
        schema_match = len(diseases) / max(len(intent_result.missing_slots) + len(diseases), 1)
        
        return StructuredResult(
            schema_match_rate=schema_match,
            row_count=len(results),
            null_ratio=0.0 if results else 1.0,
            success=len(results) > 0,
            results=results
        )
    
    def _search_comparison(self, intent_result: IntentResult) -> StructuredResult:
        """Search for comparison between diseases."""
        diseases = intent_result.entities.get('disease', [])
        
        if len(diseases) < 2:
            return StructuredResult(
                schema_match_rate=0.0,
                row_count=0,
                null_ratio=1.0,
                success=False,
                results=[],
                error="Need two diseases for comparison"
            )
        
        # Get both diseases
        results = []
        for disease in diseases[:2]:
            if disease in self.disease_index:
                doc_id = self.disease_index[disease]
                record = self.knowledge_base[doc_id]
                results.append({
                    'disease': disease,
                    'category': record['metadata'].get('category', ''),
                    'content': record['content'],
                    'key_symptoms': record['metadata'].get('key_symptoms', [])
                })
        
        return StructuredResult(
            schema_match_rate=0.8,
            row_count=len(results),
            null_ratio=0.0 if len(results) == 2 else 0.5,
            success=len(results) >= 2,
            results=results
        )
    
    def _search_generic(self, query: str, intent_result: IntentResult) -> StructuredResult:
        """Generic keyword-based search."""
        # Search in content
        results = []
        for i, record in enumerate(self.knowledge_base):
            content = record['content'].lower()
            # Simple keyword matching
            match_count = sum(1 for word in query.split() if word.lower() in content)
            if match_count > 0:
                results.append((i, match_count))
        
        # Sort by match count
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Format output
        formatted_results = []
        for doc_id, score in results[:5]:
            record = self.knowledge_base[doc_id]
            formatted_results.append({
                'disease': record['metadata'].get('disease', ''),
                'category': record['metadata'].get('category', ''),
                'match_score': score,
                'content': record['content'][:200]
            })
        
        return StructuredResult(
            schema_match_rate=0.3,  # Low for generic search
            row_count=len(formatted_results),
            null_ratio=0.0 if formatted_results else 1.0,
            success=len(formatted_results) > 0,
            results=formatted_results
        )
    
    def get_stats(self) -> Dict:
        """Get retriever statistics."""
        return {
            'knowledge_base_size': len(self.knowledge_base),
            'disease_count': len(self.disease_index),
            'symptom_count': len(self.symptom_index),
            'category_count': len(self.category_index)
        }
