# DRSearch Backend End-to-End Testing Strategy

## Overview

This document outlines the strategy for creating comprehensive end-to-end tests that verify the actual `drsearch_backend` API request and response formats using fake LLM and embedder components for deterministic testing.

## Goals

1. **Test Real Backend API**: Use the actual `drsearch_backend` FastAPI application instead of the current simulator
2. **Deterministic Responses**: Implement fake LLM and embedder with known, predictable outputs
3. **API Contract Verification**: Validate request/response formats according to the OpenAPI schema
4. **Regression Testing**: Ensure backend changes don't break API contracts
5. **Integration Testing**: Test the full RAG pipeline with mocked external dependencies

## Architecture

### Test Environment Setup

```
┌─────────────────────────────────────────────────────────────┐
│                    E2E Test Environment                     │
├─────────────────────────────────────────────────────────────┤
│  Frontend (Next.js)  ←→  Real Backend API (FastAPI)        │
│                          ↓                                 │
│                      Fake LLM & Embedder                   │
│                          ↓                                 │
│                    Mock Vector Stores                      │
│                   (In-Memory Test Data)                    │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. **Deterministic Fake LLM**
- Extend the existing `FakeStreamingListLLM` to provide:
  - Predictable responses based on input patterns
  - Streaming support for SSE endpoints
  - Chat history awareness
  - Different response types for different test scenarios

#### 2. **Fake Embedder**
- Create deterministic embeddings based on text content
- Ensure similar queries get similar embeddings
- Support different embedding dimensions

#### 3. **Test Vector Store**
- In-memory vector store with predefined test documents
- Known document-to-embedding mappings
- Configurable retrieval results

#### 4. **API Test Harness**
- Real FastAPI backend with test configuration
- Environment variable overrides for test mode
- Isolated test database/vector store

## Implementation Plan

### Phase 1: Test Infrastructure

#### 1.1 Enhanced Fake LLM (`test_full_app/backend/fake_llm.py`)

```python
from typing import Dict, List, Iterator, Any
from langchain_community.llms.fake import FakeStreamingListLLM
from langchain.schema import AIMessage

class DeterministicFakeLLM(FakeStreamingListLLM):
    """Deterministic fake LLM for predictable testing"""
    
    def __init__(self):
        # Predefined responses for different input patterns
        self.response_patterns = {
            "what is": "This is a factual response about {topic}",
            "how to": "Here are the steps to {action}",
            "troubleshoot": "To troubleshoot {issue}, follow these steps...",
            "default": "Based on the provided documents, here is the answer..."
        }
        super().__init__(responses=["default response"])
    
    def _generate_response(self, prompt: str, context: str = "") -> str:
        """Generate deterministic response based on prompt patterns"""
        prompt_lower = prompt.lower()
        
        for pattern, template in self.response_patterns.items():
            if pattern in prompt_lower:
                # Extract topic/action from prompt for more realistic responses
                return self._format_response(template, prompt, context)
        
        return self.response_patterns["default"]
    
    def _stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """Stream response token by token"""
        response = self._generate_response(prompt, kwargs.get("context", ""))
        words = response.split()
        
        for i, word in enumerate(words):
            if i > 0:
                yield " "
            yield word
            # Simulate streaming delay
            time.sleep(0.001)
```

#### 1.2 Test Vector Store (`test_full_app/backend/test_vector_store.py`)

```python
from typing import List, Dict, Any
from langchain.schema import Document, BaseRetriever

class TestVectorStore:
    """In-memory vector store with predefined test documents"""
    
    def __init__(self):
        self.documents = self._load_test_documents()
        self.embeddings = self._generate_test_embeddings()
    
    def _load_test_documents(self) -> List[Document]:
        """Load predefined test documents"""
        return [
            Document(
                page_content="This is test document 1 about troubleshooting",
                metadata={"filename": "doc1.pdf", "part_number": "PN-001"}
            ),
            Document(
                page_content="This is test document 2 about maintenance procedures",
                metadata={"filename": "doc2.pdf", "part_number": "PN-002"}
            ),
            # Add more test documents...
        ]
    
    def similarity_search(self, query: str, k: int = 3) -> List[Document]:
        """Return relevant documents based on query keywords"""
        query_lower = query.lower()
        relevant_docs = []
        
        for doc in self.documents:
            if any(word in doc.page_content.lower() for word in query_lower.split()):
                relevant_docs.append(doc)
        
        return relevant_docs[:k]
```

#### 1.3 Test Configuration (`test_full_app/backend/test_config.py`)

```python
import os
from typing import Dict, Any

def get_test_backend_config() -> Dict[str, str]:
    """Environment variables for backend testing"""
    return {
        "AUTH_ENABLED": "False",
        "RAG_ON": "True",
        "LLM_SERVICE": "fake",
        "VECTOR_BACKEND": "test",
        "LOG_LEVEL": "INFO",
        # Add other test-specific config...
    }

def setup_test_environment():
    """Configure environment for backend testing"""
    for key, value in get_test_backend_config().items():
        os.environ[key] = value
```

### Phase 2: Test Scenarios

#### 2.1 API Contract Tests (`test_full_app/backend/test_api_contracts.py`)

```python
import pytest
import httpx
from typing import Dict, Any

class TestAPIContracts:
    """Test API request/response formats match OpenAPI schema"""
    
    def test_chat_invoke_request_format(self, backend_client):
        """Test /chat/invoke accepts correct request format"""
        payload = {
            "input": {
                "question": "What is the troubleshooting procedure?",
                "chat_history": [],
                "index_name": "TEST_INDEX",
                "num_docs_retrieved": 3
            }
        }
        
        response = backend_client.post("/chat/invoke", json=payload)
        assert response.status_code == 200
        
        # Validate response structure
        data = response.json()
        assert "output" in data
        assert "metadata" in data
        assert "run_id" in data["metadata"]
    
    def test_chat_stream_log_response_format(self, backend_client):
        """Test /chat/stream_log returns valid SSE format"""
        payload = {
            "input": {
                "question": "How to perform maintenance?",
                "chat_history": [],
                "index_name": "TEST_INDEX"
            }
        }
        
        with backend_client.stream("POST", "/chat/stream_log", json=payload) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream"
            
            # Validate SSE format
            for line in response.iter_lines():
                if line.startswith("event:"):
                    assert line in ["event: data", "event: end"]
                elif line.startswith("data:"):
                    # Validate JSON structure in data lines
                    json_data = json.loads(line[5:])  # Remove "data: " prefix
                    # Add specific validations...
```

#### 2.2 End-to-End Flow Tests (`test_full_app/backend/test_e2e_flows.py`)

```python
class TestE2EFlows:
    """Test complete request-response flows"""
    
    @pytest.mark.parametrize("test_case", [
        {
            "name": "basic_qa",
            "question": "What is the troubleshooting procedure?",
            "index_name": "TEST_INDEX",
            "expected_content": "troubleshooting",
            "expected_docs": 2
        },
        {
            "name": "chat_with_history",
            "question": "What about maintenance?",
            "chat_history": [
                {"human": "Tell me about procedures", "ai": "There are several procedures..."}
            ],
            "expected_content": "maintenance"
        }
    ])
    def test_rag_pipeline(self, backend_client, test_case):
        """Test complete RAG pipeline with different scenarios"""
        payload = {
            "input": {
                "question": test_case["question"],
                "chat_history": test_case.get("chat_history", []),
                "index_name": test_case.get("index_name", "TEST_INDEX"),
                "num_docs_retrieved": test_case.get("expected_docs", 3)
            }
        }
        
        response = backend_client.post("/chat/invoke", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        output = data["output"]
        
        # Validate expected content appears in response
        assert test_case["expected_content"].lower() in output.lower()
        
        # Validate metadata
        assert "run_id" in data["metadata"]
        assert "feedback_tokens" in data["metadata"]
```

### Phase 3: Integration with Current Test Harness

#### 3.1 Enhanced Test Runner (`test_full_app/run_backend_e2e.mjs`)

```javascript
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import path from 'path';

class BackendE2ERunner {
    constructor() {
        this.backendProcess = null;
        this.backendPort = null;
    }
    
    async startBackend() {
        // Find free port
        this.backendPort = await this.findFreePort();
        
        // Set test environment
        const env = {
            ...process.env,
            AUTH_ENABLED: 'False',
            RAG_ON: 'True',
            LLM_SERVICE: 'fake',
            VECTOR_BACKEND: 'test',
            PORT: this.backendPort.toString()
        };
        
        // Start real backend with test config
        this.backendProcess = spawn('poetry', ['run', 'uvicorn', 'app.main:app', '--port', this.backendPort], {
            cwd: 'drsearch_backend',
            env,
            stdio: 'pipe'
        });
        
        await this.waitForBackend();
    }
    
    async runTests() {
        // Run backend API tests
        const testProcess = spawn('poetry', ['run', 'pytest', 'test_full_app/backend/tests/', '-v'], {
            cwd: 'drsearch_backend',
            stdio: 'inherit'
        });
        
        return new Promise((resolve) => {
            testProcess.on('close', (code) => {
                resolve(code);
            });
        });
    }
}
```

#### 3.2 Pytest Configuration (`test_full_app/backend/conftest.py`)

```python
import pytest
import asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

@pytest.fixture(scope="session")
def backend_app():
    """Create backend app with test configuration"""
    from test_config import setup_test_environment
    setup_test_environment()
    
    from app import create_app
    return create_app()

@pytest.fixture
def backend_client(backend_app):
    """Sync HTTP client for backend API"""
    return TestClient(backend_app)

@pytest.fixture
async def async_backend_client(backend_app):
    """Async HTTP client for streaming tests"""
    async with AsyncClient(app=backend_app, base_url="http://test") as client:
        yield client
```

### Phase 4: Advanced Testing Features

#### 4.1 Response Validation (`test_full_app/backend/validators.py`)

```python
from typing import Dict, Any, List
import jsonschema

class ResponseValidator:
    """Validate API responses against OpenAPI schema"""
    
    def __init__(self, schema_path: str):
        with open(schema_path) as f:
            self.schema = json.load(f)
    
    def validate_chat_invoke_response(self, response: Dict[str, Any]):
        """Validate /chat/invoke response format"""
        schema = self.schema["components"]["schemas"]["chatInvokeResponse"]
        jsonschema.validate(response, schema)
    
    def validate_sse_event(self, event_line: str):
        """Validate SSE event format"""
        if event_line.startswith("data: "):
            data = json.loads(event_line[6:])
            # Validate data structure...
```

#### 4.2 Performance Testing (`test_full_app/backend/test_performance.py`)

```python
import time
import pytest

class TestPerformance:
    """Test API performance characteristics"""
    
    def test_response_time_under_load(self, backend_client):
        """Test response times remain acceptable"""
        start_time = time.time()
        
        response = backend_client.post("/chat/invoke", json={
            "input": {"question": "Test query", "index_name": "TEST_INDEX"}
        })
        
        end_time = time.time()
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 2.0  # Should respond within 2 seconds
    
    def test_streaming_latency(self, backend_client):
        """Test streaming response starts quickly"""
        start_time = time.time()
        first_token_time = None
        
        with backend_client.stream("POST", "/chat/stream_log", json={
            "input": {"question": "Stream test", "index_name": "TEST_INDEX"}
        }) as response:
            for line in response.iter_lines():
                if first_token_time is None and line.startswith("data:"):
                    first_token_time = time.time()
                    break
        
        if first_token_time:
            latency = first_token_time - start_time
            assert latency < 1.0  # First token within 1 second
```

## Benefits of This Approach

1. **Real API Testing**: Tests the actual FastAPI application and LangChain integration
2. **Deterministic Results**: Fake components provide predictable outputs for reliable testing
3. **Schema Validation**: Automatically validates API contracts against OpenAPI specification
4. **Regression Prevention**: Catches breaking changes to API request/response formats
5. **Performance Monitoring**: Tracks response times and streaming latency
6. **Comprehensive Coverage**: Tests both successful flows and error conditions

## Migration Path

1. **Phase 1**: Implement fake components and basic test infrastructure
2. **Phase 2**: Create core API contract tests
3. **Phase 3**: Add comprehensive flow testing
4. **Phase 4**: Integrate with existing test harness
5. **Phase 5**: Add advanced features (performance, load testing)

This strategy provides a robust foundation for testing the actual backend API while maintaining the benefits of deterministic, fast-running tests. 