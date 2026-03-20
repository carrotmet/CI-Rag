"""LLM Client using litellm for Level 2 semantic refinement.

Provides unified interface for multi-provider LLM access with:
- Configurable model routing
- Automatic fallback chains
- Cost tracking
- Async support
"""

import os
import time
import yaml
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from pathlib import Path

# Optional litellm import
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    print("Warning: litellm not available. Install: pip install litellm>=1.0.0")


@dataclass
class LLMResponse:
    """Structured LLM response."""
    content: str
    model: str
    latency_ms: float
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None
    raw_response: Any = None


@dataclass
class LLMConfig:
    """LLM configuration."""
    model: str = "kimi-k2-turbo-preview"
    temperature: float = 0.3
    max_tokens: int = 2000
    timeout: int = 30
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    response_format: Optional[Dict] = field(default_factory=lambda: {"type": "json_object"})
    fallback_models: List[str] = field(default_factory=list)


class LLMClient:
    """
    Unified LLM client with litellm backend.
    
    Features:
    - YAML config loading
    - Environment variable substitution
    - Automatic fallback on failure
    - Cost and latency tracking
    """
    
    DEFAULT_CONFIG_PATH = "config/llm_config.yaml"
    
    def __init__(self, config_path: Optional[str] = None, model_alias: Optional[str] = None):
        """
        Initialize LLM client.
        
        Args:
            config_path: Path to YAML config file
            model_alias: Model alias to use (e.g., 'ci-evaluation', 'complex-analysis')
        """
        if not LITELLM_AVAILABLE:
            raise ImportError("litellm required. Install: pip install litellm>=1.0.0")
        
        self.config_path = config_path or self._find_config()
        self.config = self._load_config()
        self.model_alias = model_alias or "default"
        self.model_config = self._resolve_model_config(self.model_alias)
        
        # Metrics tracking
        self.total_requests = 0
        self.total_cost = 0.0
        self.total_latency = 0.0
        
        # Suppress verbose litellm logging
        litellm.set_verbose = False
    
    def _find_config(self) -> str:
        """Find config file in standard locations."""
        paths = [
            os.environ.get("CI_LLM_CONFIG", ""),
            "config/llm_config.yaml",
            "../config/llm_config.yaml",
            "../../config/llm_config.yaml",
        ]
        for path in paths:
            if path and Path(path).exists():
                return path
        return self.DEFAULT_CONFIG_PATH
    
    def _load_config(self) -> Dict:
        """Load and parse YAML config with env var substitution."""
        if not Path(self.config_path).exists():
            print(f"Warning: Config file not found: {self.config_path}")
            return {}
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Substitute environment variables
        content = self._substitute_env_vars(content)
        
        return yaml.safe_load(content) or {}
    
    def _substitute_env_vars(self, content: str) -> str:
        """Substitute ${VAR} with environment variable values."""
        import re
        
        def replace_var(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        
        return re.sub(r'\$\{([^}]+)\}', replace_var, content)
    
    def _resolve_model_config(self, alias: str) -> LLMConfig:
        """Resolve model alias to concrete configuration."""
        model_list = self.config.get("model_list", [])
        model_alias_map = self.config.get("model_alias", {})
        
        # Resolve alias to model name
        model_name = model_alias_map.get(alias, alias)
        
        # Find model config
        for model_def in model_list:
            if model_def.get("model_name") == model_name:
                params = model_def.get("litellm_params", {})
                
                # Build fallback list
                fallbacks = []
                fallback_strategy = self.config.get("router_settings", {}).get("fallback_strategy", [])
                for strategy in fallback_strategy:
                    if strategy.get("model") == model_name:
                        fallbacks = strategy.get("fallback", [])
                        break
                
                return LLMConfig(
                    model=params.get("model", model_name),
                    temperature=params.get("temperature", 0.3),
                    max_tokens=params.get("max_tokens", 2000),
                    timeout=params.get("timeout", 30),
                    api_key=params.get("api_key"),
                    api_base=params.get("api_base"),
                    response_format=params.get("response_format", {"type": "json_object"}),
                    fallback_models=fallbacks
                )
        
        # Default config if not found
        return LLMConfig(model=model_name)
    
    def complete(self, 
                 messages: List[Dict[str, str]], 
                 model: Optional[str] = None,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 response_format: Optional[Dict] = None) -> LLMResponse:
        """
        Execute LLM completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Override model name
            temperature: Override temperature
            max_tokens: Override max tokens
            response_format: Override response format
            
        Returns:
            LLMResponse with content and metadata
        """
        start_time = time.time()
        self.total_requests += 1
        
        config = self.model_config
        model_name = model or config.model
        
        # Build kwargs
        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else config.max_tokens,
            "timeout": config.timeout,
        }
        
        # Add optional params
        if config.api_key:
            kwargs["api_key"] = config.api_key
        if config.api_base:
            kwargs["api_base"] = config.api_base
        if response_format or config.response_format:
            kwargs["response_format"] = response_format or config.response_format
        
        # Try primary model, then fallbacks
        models_to_try = [model_name] + config.fallback_models
        last_error = None
        
        for attempt_model in models_to_try:
            try:
                kwargs["model"] = attempt_model
                response = litellm.completion(**kwargs)
                
                latency_ms = (time.time() - start_time) * 1000
                self.total_latency += latency_ms
                
                # Extract usage
                usage = response.get("usage", {})
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)
                
                # Estimate cost (rough estimate for Kimi models)
                cost = self._estimate_cost(attempt_model, tokens_in, tokens_out)
                self.total_cost += cost
                
                content = response["choices"][0]["message"]["content"]
                
                return LLMResponse(
                    content=content,
                    model=attempt_model,
                    latency_ms=latency_ms,
                    tokens_input=tokens_in,
                    tokens_output=tokens_out,
                    cost_usd=cost,
                    success=True,
                    raw_response=response
                )
                
            except Exception as e:
                last_error = str(e)
                print(f"Model {attempt_model} failed: {e}")
                continue
        
        # All models failed
        latency_ms = (time.time() - start_time) * 1000
        return LLMResponse(
            content="",
            model=model_name,
            latency_ms=latency_ms,
            success=False,
            error=last_error
        )
    
    def complete_simple(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """
        Simple completion with single prompt.
        
        Args:
            prompt: User prompt
            system: Optional system message
            **kwargs: Additional params for complete()
            
        Returns:
            Response content string
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        response = self.complete(messages, **kwargs)
        return response.content if response.success else ""
    
    def _estimate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Estimate cost in USD (rough estimates for Kimi models)."""
        # Kimi pricing (approximate)
        pricing = {
            "openai/kimi-k2-turbo-preview": (0.0005, 0.0015),  # $/1K tokens
            "openai/kimi-k2.5": (0.001, 0.003),
            "openai/moonshot-v1-8k": (0.0003, 0.0006),
        }
        
        input_price, output_price = pricing.get(model, (0.001, 0.002))
        
        cost = (tokens_in / 1000 * input_price) + (tokens_out / 1000 * output_price)
        return cost
    
    def get_metrics(self) -> Dict:
        """Get usage metrics."""
        return {
            "total_requests": self.total_requests,
            "total_cost_usd": round(self.total_cost, 6),
            "avg_latency_ms": round(self.total_latency / max(self.total_requests, 1), 2),
            "model": self.model_alias
        }
    
    def switch_model(self, alias: str):
        """Switch to different model alias."""
        self.model_alias = alias
        self.model_config = self._resolve_model_config(alias)


# Convenience function
def create_llm_client(config_path: Optional[str] = None, 
                      model_alias: str = "default") -> LLMClient:
    """Create LLM client with specified alias."""
    return LLMClient(config_path=config_path, model_alias=model_alias)
