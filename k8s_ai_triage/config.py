"""
Configuration Management Module

This module handles all application configuration by loading settings from environment
variables defined in the .env file. It provides a centralized Config class that manages:

- Gemini API credentials and LLM settings (model, temperature, token limits)
- Kubernetes cluster connection details (namespace, context, cluster name)
- Application settings (logging level, output format)

The configuration follows a singleton pattern to ensure consistent settings across
the entire application. All settings can be overridden programmatically when needed.

Key Features:
- Automatic .env file loading on module import
- Type conversion for numeric values (int, float)
- Validation for required fields (GEMINI_API_KEY)
- Sensible defaults for all optional settings
- Runtime override capability for testing and flexibility

Usage:
    from k8s_ai_triage.config import get_config
    
    config = get_config()
    config.validate_required()  # Raises ValueError if API key missing
    print(config.k8s_namespace)  # Access settings
    
    # Override settings
    config = get_config(k8s_namespace="production")

Environment Variables:
    GEMINI_API_KEY: Google Gemini API key (required)
    K8S_CLUSTER_NAME: Kubernetes cluster identifier (optional)
    K8S_NAMESPACE: Default namespace for pod analysis (default: "default")
    K8S_CONTEXT: Specific kubectl context to use (optional)
    LLM_MODEL: Gemini model name (default: "gemini-2.0-flash-exp")
    LLM_TEMPERATURE: LLM temperature 0.0-1.0 (default: 0.1 for deterministic output)
    LLM_MAX_LOG_LINES: Max log lines sent to LLM for cost control (default: 200)
    LOG_LEVEL: Logging verbosity (default: "INFO")
    OUTPUT_FORMAT: Default output format "markdown" or "json" (default: "markdown")
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    def __init__(self):
        # Gemini API
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        
        # Kubernetes
        self.k8s_cluster_name = os.getenv("K8S_CLUSTER_NAME", "")
        self.k8s_namespace = os.getenv("K8S_NAMESPACE", "default")
        self.k8s_context = os.getenv("K8S_CONTEXT", "") or None
        
        # LLM settings
        self.llm_model = os.getenv("LLM_MODEL", "gemini-2.0-flash-exp")
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
        self.llm_max_log_lines = int(os.getenv("LLM_MAX_LOG_LINES", "200"))
        
        # App settings
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.output_format = os.getenv("OUTPUT_FORMAT", "markdown")
    
    def validate_required(self):
        """Validate required configuration."""
        if not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is required. "
                "Please set it in your .env file. "
                "Get your key at: https://aistudio.google.com/app/apikey"
            )


_config = None


def get_config(**overrides):
    """Get configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    
    # Apply overrides
    for key, value in overrides.items():
        if hasattr(_config, key) and value is not None:
            setattr(_config, key, value)
    
    return _config
