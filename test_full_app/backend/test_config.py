import os
from typing import Dict


_TEST_ENV: Dict[str, str] = {
    "AUTH_ENABLED": "False",
    "RAG_ON": "True",
    "LLM_SERVICE": "fake",
    "VECTOR_BACKEND": "test",
    "LOG_LEVEL": "INFO",
    "WEAVIATE_URL": "http://test:8080",
    "WEAVIATE_API_KEY": "test-key",
    "AZURE_OPENAI_API_VERSION": "2024-05-15",
    "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model",
    "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
    "AZURE_OPENAI_API_KEY": "test-key",
    "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
    "AZURE_SEARCH_KEY": "test-key",
    "PGVECTOR_URL": "postgresql://test:test@localhost/test",
    "CORS_ORIGINS": '["http://localhost:3000"]',
}


def get_test_backend_config() -> Dict[str, str]:
    """Return environment variables for backend testing."""
    return _TEST_ENV.copy()


def setup_test_environment(extra: Dict[str, str] | None = None) -> Dict[str, str]:
    """Apply backend test environment variables."""
    env = get_test_backend_config()
    if extra:
        env.update(extra)
    for key, value in env.items():
        os.environ[key] = value
    
    # Clear the settings cache so new environment variables are picked up
    try:
        from app.core.config import get_settings
        get_settings.cache_clear()
    except ImportError:
        pass  # App not available in test context
    
    return env
