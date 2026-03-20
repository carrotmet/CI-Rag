"""Response Parser for Level 2 LLM outputs.

Handles JSON extraction, validation, and error recovery.
"""

import re
import json
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ParsedResponse:
    """Parsed LLM response with validation status."""
    C: int  # Complexity: 0 or 1
    I: int  # Information sufficiency: 0 or 1
    confidence: float  # 0.0 - 1.0
    reasoning: str
    missing_info: list
    raw_content: str
    success: bool
    error: Optional[str] = None
    parse_failures: int = 0


class ResponseParser:
    """
    Parse and validate LLM responses for Level 2 arbitration.
    
    Features:
    - JSON extraction from various formats
    - Field validation and normalization
    - Error recovery with partial parsing
    - Consistency checking
    """
    
    # Valid values for discrete CI
    VALID_C = {0, 1}
    VALID_I = {0, 1}
    
    def __init__(self, max_parse_failures: int = 3):
        """
        Initialize parser.
        
        Args:
            max_parse_failures: Max failures before triggering fallback
        """
        self.max_parse_failures = max_parse_failures
        self.parse_failure_count = 0
    
    def parse(self, content: str) -> ParsedResponse:
        """
        Parse LLM response content.
        
        Args:
            content: Raw LLM output
            
        Returns:
            ParsedResponse with extracted fields
        """
        if not content or not content.strip():
            self.parse_failure_count += 1
            return self._create_error_response(content, "Empty response")
        
        # Try to extract JSON
        json_data = self._extract_json(content)
        
        if json_data is None:
            self.parse_failure_count += 1
            return self._create_error_response(content, "No valid JSON found")
        
        # Validate and extract fields
        try:
            result = self._validate_and_extract(json_data, content)
            if result.success:
                self.parse_failure_count = 0  # Reset on success
            else:
                self.parse_failure_count += 1
            result.parse_failures = self.parse_failure_count
            return result
        except Exception as e:
            self.parse_failure_count += 1
            return self._create_error_response(content, f"Validation error: {e}")
    
    def _extract_json(self, content: str) -> Optional[Dict]:
        """
        Extract JSON from various formats.
        
        Attempts:
        1. Direct JSON parsing
        2. JSON within markdown code blocks
        3. JSON within plain text
        4. Partial JSON extraction
        """
        content = content.strip()
        
        # Attempt 1: Direct parsing
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Attempt 2: Markdown code blocks
        patterns = [
            r'```json\s*(.*?)\s*```',  # ```json ... ```
            r'```\s*(.*?)\s*```',       # ``` ... ```
            r'`\s*(.*?)\s*`',           # ` ... `
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue
        
        # Attempt 3: Find JSON-like structure
        json_pattern = r'\{[^{}]*\}'
        for match in re.finditer(json_pattern, content, re.DOTALL):
            try:
                # Try to parse with nested structure support
                potential_json = match.group(0)
                # Check for nested braces
                start = match.start()
                end = self._find_matching_brace(content, start)
                if end > start:
                    potential_json = content[start:end+1]
                return json.loads(potential_json)
            except (json.JSONDecodeError, ValueError):
                continue
        
        # Attempt 4: Extract key-value pairs manually
        return self._extract_key_value_pairs(content)
    
    def _find_matching_brace(self, text: str, start: int) -> int:
        """Find matching closing brace for opening brace at start."""
        count = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                count += 1
            elif text[i] == '}':
                count -= 1
                if count == 0:
                    return i
        return -1
    
    def _extract_key_value_pairs(self, content: str) -> Optional[Dict]:
        """Extract key-value pairs as fallback."""
        result = {}
        
        # Look for C value
        c_match = re.search(r'["\']?C["\']?\s*[:=]\s*(\d)', content)
        if c_match:
            result['C'] = int(c_match.group(1))
        
        # Look for I value
        i_match = re.search(r'["\']?I["\']?\s*[:=]\s*(\d)', content)
        if i_match:
            result['I'] = int(i_match.group(1))
        
        # Look for confidence
        conf_match = re.search(r'["\']?confidence["\']?\s*[:=]\s*(\d+\.?\d*)', content, re.IGNORECASE)
        if conf_match:
            result['confidence'] = float(conf_match.group(1))
        
        # Look for reasoning
        reason_match = re.search(r'["\']?reasoning["\']?\s*[:=]\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
        if reason_match:
            result['reasoning'] = reason_match.group(1)
        
        return result if result else None
    
    def _validate_and_extract(self, data: Dict, raw_content: str) -> ParsedResponse:
        """Validate and extract fields from parsed JSON."""
        errors = []
        
        # Extract C (Complexity)
        C = data.get('C')
        if C is None:
            # Try alternative keys
            C = data.get('complexity', data.get('c'))
        
        if C is None:
            errors.append("Missing 'C' field")
            C = 0  # Default to low complexity (conservative)
        else:
            C = int(C)
            if C not in self.VALID_C:
                errors.append(f"Invalid C value: {C}, expected 0 or 1")
                C = 1 if C > 1 else 0  # Clamp to valid range
        
        # Extract I (Information sufficiency)
        I = data.get('I')
        if I is None:
            # Try alternative keys
            I = data.get('information', data.get('i', data.get('information_sufficiency')))
        
        if I is None:
            errors.append("Missing 'I' field")
            I = 0  # Default to insufficient (conservative)
        else:
            I = int(I)
            if I not in self.VALID_I:
                errors.append(f"Invalid I value: {I}, expected 0 or 1")
                I = 1 if I > 1 else 0  # Clamp to valid range
        
        # Extract confidence
        confidence = data.get('confidence', 0.5)
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        except (ValueError, TypeError):
            errors.append(f"Invalid confidence value: {confidence}")
            confidence = 0.5
        
        # Extract reasoning
        reasoning = data.get('reasoning', '')
        if not reasoning:
            reasoning = data.get('reason', data.get('explanation', ''))
        reasoning = str(reasoning)[:500]  # Limit length
        
        # Extract missing_info
        missing_info = data.get('missing_info', [])
        if not isinstance(missing_info, list):
            if isinstance(missing_info, str):
                missing_info = [missing_info]
            else:
                missing_info = []
        
        # Extract additional fields
        complexity_score = data.get('complexity_score')
        information_score = data.get('information_score')
        recommended_zone = data.get('recommended_zone')
        
        success = len(errors) == 0
        error_msg = "; ".join(errors) if errors else None
        
        response = ParsedResponse(
            C=C,
            I=I,
            confidence=confidence,
            reasoning=reasoning,
            missing_info=missing_info,
            raw_content=raw_content,
            success=success,
            error=error_msg,
            parse_failures=self.parse_failure_count
        )
        
        # Attach additional fields as metadata
        if complexity_score is not None:
            response.complexity_score = complexity_score
        if information_score is not None:
            response.information_score = information_score
        if recommended_zone is not None:
            response.recommended_zone = recommended_zone
        
        return response
    
    def _create_error_response(self, content: str, error: str) -> ParsedResponse:
        """Create error response with conservative defaults."""
        return ParsedResponse(
            C=1,  # Conservative: assume high complexity
            I=0,  # Conservative: assume insufficient info
            confidence=0.3,  # Low confidence
            reasoning="Parse error - using conservative defaults",
            missing_info=["Parse error occurred"],
            raw_content=content,
            success=False,
            error=error,
            parse_failures=self.parse_failure_count
        )
    
    def should_fallback(self) -> bool:
        """Check if parser has exceeded max failure threshold."""
        return self.parse_failure_count >= self.max_parse_failures
    
    def reset_failures(self):
        """Reset failure counter."""
        self.parse_failure_count = 0
    
    @staticmethod
    def calculate_consistency(probe1: ParsedResponse, 
                               probe2: ParsedResponse) -> float:
        """
        Calculate Jaccard-like consistency between two probes.
        
        Returns:
            Consistency score 0.0 - 1.0
        """
        if not probe1.success or not probe2.success:
            return 0.0
        
        # Compare C values
        c_match = probe1.C == probe2.C
        
        # Compare I values
        i_match = probe1.I == probe2.I
        
        # Compare confidence (within 0.2 tolerance)
        conf_diff = abs(probe1.confidence - probe2.confidence)
        conf_similar = conf_diff < 0.2
        
        # Weighted score
        score = 0.0
        if c_match:
            score += 0.35
        if i_match:
            score += 0.35
        if conf_similar:
            score += 0.30
        
        return score


def parse_llm_response(content: str, 
                       max_failures: int = 3) -> ParsedResponse:
    """
    Convenience function to parse LLM response.
    
    Args:
        content: Raw LLM output
        max_failures: Max allowed parse failures
        
    Returns:
        ParsedResponse
    """
    parser = ResponseParser(max_parse_failures=max_failures)
    return parser.parse(content)
