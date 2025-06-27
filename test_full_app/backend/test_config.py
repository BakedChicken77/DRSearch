import os

# Centralized environment variables for backend E2E tests
TEST_ENV_VARS = {
    "AUTH_ENABLED": "False",
    "RAG_ON": "True",
    "LLM_SERVICE": "azure",
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


def apply_test_environment() -> None:
    """Apply environment variables for backend tests."""
    for key, value in TEST_ENV_VARS.items():
        os.environ[key] = value
