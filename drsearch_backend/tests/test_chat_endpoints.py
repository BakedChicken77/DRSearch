"""Tests for the refactored chat endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app import create_app
from app.models import ChatRequest


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_chat_request():
    """Sample chat request for testing."""
    return {
        "question": "What is the capital of France?",
        "chat_history": [{"human": "Hello", "ai": "Hi there!"}],
        "index_name": "test_index",
        "num_docs_retrieved": 3
    }


@patch('app.api.v1.routes.run_agent')
def test_chat_invoke_success(mock_run_agent, client, sample_chat_request):
    """Test the /chat/invoke endpoint returns a successful response."""
    # Mock the agent response
    mock_run_agent.return_value = "Paris is the capital of France."
    
    response = client.post("/chat/invoke", json=sample_chat_request)
    
    assert response.status_code == 200
    data = response.json()
    assert "output" in data
    assert data["output"] == "Paris is the capital of France."
    assert "metadata" in data
    assert "run_id" in data["metadata"]
    
    # Verify the agent was called with correct parameters
    mock_run_agent.assert_called_once()
    call_args = mock_run_agent.call_args[0]
    assert call_args[0] == "What is the capital of France?"
    assert "User: Hello" in call_args[1]
    assert "Assistant: Hi there!" in call_args[1]


@patch('app.api.v1.routes.run_agent')
def test_chat_invoke_error_handling(mock_run_agent, client, sample_chat_request):
    """Test the /chat/invoke endpoint handles errors correctly."""
    # Mock the agent to raise an exception
    mock_run_agent.side_effect = Exception("Agent error")
    
    response = client.post("/chat/invoke", json=sample_chat_request)
    
    assert response.status_code == 500
    assert "Agent error" in response.json()["detail"]


@patch('app.api.v1.routes.run_agent')
def test_chat_stream_success(mock_run_agent, client, sample_chat_request):
    """Test the /chat/stream endpoint returns a streaming response."""
    # Mock the agent response
    mock_run_agent.return_value = "Paris is the capital of France."
    
    response = client.post("/chat/stream", json=sample_chat_request)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    
    # Read the streaming response
    content = response.content.decode()
    assert "Paris" in content
    assert "capital" in content
    assert "France" in content


@patch('app.api.v1.routes.run_agent')
def test_chat_stream_log_success(mock_run_agent, client, sample_chat_request):
    """Test the /chat/stream_log endpoint returns a streaming response with logs."""
    # Mock the agent response
    mock_run_agent.return_value = "Paris is the capital of France."
    
    response = client.post("/chat/stream_log", json=sample_chat_request)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    
    # Read the streaming response
    content = response.content.decode()
    
    # Check for Langserve-compatible format
    assert "data:" in content
    assert "op" in content
    assert "path" in content
    assert "value" in content
    assert "Paris" in content


def test_chat_invoke_validation_error(client):
    """Test the /chat/invoke endpoint validates request data."""
    # Send invalid request (missing required field)
    invalid_request = {"chat_history": []}
    
    response = client.post("/chat/invoke", json=invalid_request)
    
    assert response.status_code == 422  # Validation error


def test_chat_endpoints_exist(client):
    """Test that all expected chat endpoints exist."""
    # Test that the endpoints exist by checking their OpenAPI schema
    response = client.get("/openapi.json")
    assert response.status_code == 200
    
    openapi_data = response.json()
    paths = openapi_data["paths"]
    
    assert "/chat/invoke" in paths
    assert "/chat/stream" in paths
    assert "/chat/stream_log" in paths
    
    # Verify they're POST endpoints
    assert "post" in paths["/chat/invoke"]
    assert "post" in paths["/chat/stream"]
    assert "post" in paths["/chat/stream_log"]