"""
Example end-to-end test demonstrating how to test the real drsearch_backend API
with fake LLM and embedder components for deterministic results.

This is a working example that can be run immediately to test the backend API
without external dependencies.
"""

import json
import os
import sys
import pytest
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from unittest.mock import patch
from pathlib import Path

from test_config import apply_test_environment, TEST_ENV_VARS

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent.parent / "drsearch_backend"
test_components_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(test_components_dir))

# Import the fake components
try:
    from fake_components import (
        DeterministicFakeLLM,
        DeterministicFakeEmbeddings,
        FakeVectorRetriever,
        create_test_llm,
        create_test_embeddings,
        create_test_retriever,
    )
except ImportError as e:
    print(f"Failed to import fake components: {e}")
    pytest.skip("fake_components not available", allow_module_level=True)


class TestBackendE2EExample:
    """
    Example end-to-end tests for the drsearch_backend API.

    These tests demonstrate how to:
    1. Use the real FastAPI backend with fake components
    2. Verify API request/response formats
    3. Test streaming endpoints
    4. Validate different query patterns
    """

    @pytest.fixture(scope="class")
    def backend_app(self):
        """Create the real backend app with test configuration."""
        apply_test_environment()

        # Patch the backend components with our fake implementations
        try:
            with patch("app.chain.engine.AzureChatOpenAI", create_test_llm), patch(
                "app.chain.embeddings.AzureOpenAIEmbeddings", create_test_embeddings
            ), patch(
                "app.chain.retriever.RetrieverFactory.build", create_test_retriever
            ):

                from app import create_app

                yield create_app()
        except ImportError as e:
            # Fallback if imports fail
            print(f"Import error: {e}")
            pytest.skip("Could not import backend app")

    @pytest.fixture
    def client(self, backend_app):
        """Create a test client for the backend API."""
        return TestClient(backend_app)

    def test_index_options_endpoint(self, client):
        """Test the /index-options endpoint returns correct format."""
        response = client.get("/index-options")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "result" in data
        assert "code" in data
        assert data["code"] == 200
        assert isinstance(data["result"], list)

        # Validate each index option
        for index_option in data["result"]:
            assert "name" in index_option
            assert "display_name" in index_option
            assert "initialized" in index_option
            assert "example_questions" in index_option

    def test_chat_invoke_basic_query(self, client):
        """Test /chat/invoke with a basic troubleshooting query."""
        payload = {
            "input": {
                "question": "How to troubleshoot system errors?",
                "chat_history": [],
                "index_name": "TEST_INDEX",
                "num_docs_retrieved": 3,
            }
        }

        response = client.post("/chat/invoke", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "output" in data
        assert "metadata" in data

        # Validate metadata
        metadata = data["metadata"]
        assert "run_id" in metadata

        # Validate output content
        output = data["output"]
        assert isinstance(output, str)
        assert len(output) > 0

        # Since we use deterministic fake LLM, we can test specific content
        assert "troubleshoot" in output.lower()
        assert "steps" in output.lower()

    def test_chat_invoke_maintenance_query(self, client):
        """Test /chat/invoke with a maintenance query."""
        payload = {
            "input": {
                "question": "What are the maintenance procedures?",
                "chat_history": [],
                "index_name": "TEST_INDEX",
                "num_docs_retrieved": 2,
            }
        }

        response = client.post("/chat/invoke", json=payload)

        assert response.status_code == 200
        data = response.json()

        output = data["output"]
        # Deterministic fake LLM should return maintenance-specific content
        assert "maintenance" in output.lower()
        assert "safety" in output.lower() or "procedures" in output.lower()

    def test_chat_invoke_with_history(self, client):
        """Test /chat/invoke with chat history."""
        payload = {
            "input": {
                "question": "What about error handling?",
                "chat_history": [
                    {
                        "human": "Tell me about troubleshooting",
                        "ai": "Troubleshooting involves systematic diagnosis...",
                    }
                ],
                "index_name": "TEST_INDEX",
                "num_docs_retrieved": 3,
            }
        }

        response = client.post("/chat/invoke", json=payload)

        assert response.status_code == 200
        data = response.json()

        output = data["output"]
        # Should include follow-up context
        assert len(output) > 0
        assert "troubleshoot" in output.lower()

    def test_chat_stream_log_format(self, client):
        """Test /chat/stream_log returns proper SSE format."""
        payload = {
            "input": {
                "question": "How to perform system maintenance?",
                "chat_history": [],
                "index_name": "TEST_INDEX",
            }
        }

        with client.stream("POST", "/chat/stream_log", json=payload) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            # Collect streaming events
            events = []
            current_event = {}

            for line in response.iter_lines():
                line = line.decode() if isinstance(line, bytes) else line

                if line.startswith("event:"):
                    if current_event:
                        events.append(current_event)
                    current_event = {"event": line[6:].strip()}
                elif line.startswith("data:"):
                    current_event["data"] = line[5:].strip()
                elif line == "":
                    # Empty line indicates end of event
                    if current_event:
                        events.append(current_event)
                        current_event = {}

            # Validate events
            assert len(events) > 0

            # Should have data events and end event
            data_events = [e for e in events if e.get("event") == "data"]
            end_events = [e for e in events if e.get("event") == "end"]

            assert len(data_events) > 0
            assert len(end_events) == 1

            # Validate data event structure
            for event in data_events:
                if event.get("data"):
                    # Should be valid JSON
                    data = json.loads(event["data"])
                    assert isinstance(data, dict)

    def test_chat_batch_multiple_queries(self, client):
        """Test /chat/batch with multiple queries."""
        payload = {
            "inputs": [
                {
                    "question": "How to troubleshoot errors?",
                    "chat_history": [],
                    "index_name": "TEST_INDEX",
                    "num_docs_retrieved": 2,
                },
                {
                    "question": "What are maintenance procedures?",
                    "chat_history": [],
                    "index_name": "TEST_INDEX",
                    "num_docs_retrieved": 2,
                },
            ]
        }

        response = client.post("/chat/batch", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Validate batch response structure
        assert "output" in data
        assert "metadata" in data

        # Should have responses for both inputs
        outputs = data["output"]
        assert len(outputs) == 2

        # Each output should be a string
        for output in outputs:
            assert isinstance(output, str)
            assert len(output) > 0

        # Validate metadata
        metadata = data["metadata"]
        assert "run_ids" in metadata
        assert len(metadata["run_ids"]) == 2

    def test_api_schema_endpoints(self, client):
        """Test schema endpoints return valid schemas."""
        schema_endpoints = [
            "/chat/input_schema",
            "/chat/output_schema",
            "/chat/config_schema",
        ]

        for endpoint in schema_endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200

            # Should return valid JSON schema
            schema = response.json()
            assert isinstance(schema, dict)

    def test_feedback_endpoint(self, client):
        """Test feedback endpoint accepts valid feedback."""
        # First, make a request to get a run_id
        chat_payload = {
            "input": {
                "question": "Test query for feedback",
                "chat_history": [],
                "index_name": "TEST_INDEX",
            }
        }

        chat_response = client.post("/chat/invoke", json=chat_payload)
        assert chat_response.status_code == 200

        run_id = chat_response.json()["metadata"]["run_id"]

        # Now submit feedback
        feedback_payload = {"run_id": run_id, "score": 5, "comment": "Test feedback"}

        feedback_response = client.post("/feedback", json=feedback_payload)
        assert feedback_response.status_code == 200

        feedback_data = feedback_response.json()
        assert "result" in feedback_data
        assert "code" in feedback_data

    def test_error_handling(self, client):
        """Test API error handling."""
        # Test with invalid payload
        invalid_payload = {
            "input": {
                # Missing required question field
                "chat_history": [],
                "index_name": "TEST_INDEX",
            }
        }

        response = client.post("/chat/invoke", json=invalid_payload)
        assert response.status_code == 422  # Validation error

        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.parametrize(
        "query_type,expected_content",
        [
            ("troubleshoot", "troubleshoot"),
            ("maintenance", "maintenance"),
            ("error handling", "error"),
            ("part number PN-123", "part"),
            ("what is system configuration", "documentation"),
            ("how to restart system", "instructions"),
        ],
    )
    def test_deterministic_responses(self, client, query_type, expected_content):
        """Test that fake LLM produces deterministic responses for different query types."""
        payload = {
            "input": {
                "question": query_type,
                "chat_history": [],
                "index_name": "TEST_INDEX",
                "num_docs_retrieved": 3,
            }
        }

        # Make the same request twice
        response1 = client.post("/chat/invoke", json=payload)
        response2 = client.post("/chat/invoke", json=payload)

        assert response1.status_code == 200
        assert response2.status_code == 200

        output1 = response1.json()["output"]
        output2 = response2.json()["output"]

        # Responses should be identical (deterministic)
        assert output1 == output2

        # Should contain expected content
        assert expected_content.lower() in output1.lower()

    def test_unknown_index_defaults_to_chatbot(self, client):
        """Unknown index names should still return a valid response."""
        payload = {
            "input": {
                "question": "General question",
                "chat_history": [],
                "index_name": "UNKNOWN_INDEX",
                "num_docs_retrieved": 1,
            }
        }

        response = client.post("/chat/invoke", json=payload)
        assert response.status_code == 200
        assert response.json()["output"]


class TestSimulatorEdgeCases:
    """Edge case tests using the backend simulator."""

    @pytest.fixture(scope="class")
    def sim_client(self):
        from simulator import app as sim_app

        return TestClient(sim_app)

    def test_malformed_sse_stream(self, sim_client):
        """Simulator should include garbage lines when MALFORMED_SSE is used."""
        payload = {"input": {"question": "X", "index_name": "MALFORMED_SSE"}}
        with sim_client.stream("POST", "/chat/stream_log", json=payload) as resp:
            assert resp.status_code == 200
            lines = list(resp.iter_lines())
            assert any("garbage" in line for line in lines)
            assert any("event: end" in line for line in lines)

    def test_error_response(self, sim_client):
        """Simulator returns 500 for ERROR_500 index."""
        payload = {"input": {"question": "X", "index_name": "ERROR_500"}}
        resp = sim_client.post("/chat/stream_log", json=payload)
        assert resp.status_code == 500
        assert "backend failure" in resp.text


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
