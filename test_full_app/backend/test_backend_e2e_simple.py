"""
Simplified end-to-end test demonstrating fake components for backend API testing.

This test focuses on demonstrating the fake components work correctly without
requiring the full backend app (which has Pydantic version compatibility issues).
"""

import json
import os
import sys
import pytest
from typing import Dict, Any, List
from pathlib import Path

# Add the test components directory to Python path
test_components_dir = Path(__file__).parent
sys.path.insert(0, str(test_components_dir))

# Import the fake components
try:
    from fake_components import (
        DeterministicFakeLLM, 
        DeterministicFakeEmbeddings, 
        FakeVectorRetriever,
        create_test_llm,
        create_test_embeddings,
        create_test_retriever
    )
except ImportError as e:
    print(f"Failed to import fake components: {e}")
    pytest.skip("fake_components not available", allow_module_level=True)


class TestFakeComponents:
    """Test the fake components work correctly for backend testing."""
    
    def test_fake_llm_basic_responses(self):
        """Test that fake LLM generates appropriate responses for different query types."""
        llm = DeterministicFakeLLM()
        
        # Test troubleshooting query
        response = llm._call("How to troubleshoot system errors?")
        assert "troubleshoot" in response.lower()
        assert "steps" in response.lower()
        
        # Test maintenance query
        response = llm._call("What are the maintenance procedures?")
        assert "maintenance" in response.lower()
        assert "safety" in response.lower() or "procedures" in response.lower()
        
        # Test part number query
        response = llm._call("What is part number PN-123?")
        assert "part" in response.lower() or "component" in response.lower()
    
    def test_fake_llm_deterministic(self):
        """Test that fake LLM produces deterministic responses."""
        llm = DeterministicFakeLLM()
        
        query = "How to troubleshoot system errors?"
        response1 = llm._call(query)
        response2 = llm._call(query)
        
        # Should be identical
        assert response1 == response2
    
    def test_fake_llm_multiquery_compatibility(self):
        """Test that fake LLM handles MultiQueryRetriever-style prompts."""
        llm = DeterministicFakeLLM()
        
        # Simulate MultiQueryRetriever prompt
        multiquery_prompt = "Generate 3 similar questions for: How to troubleshoot?"
        response = llm._call(multiquery_prompt)
        
        # Should return multiple questions separated by newlines
        lines = response.split('\n')
        assert len(lines) >= 2  # Should have multiple questions
        assert any("troubleshoot" in line.lower() for line in lines)
    
    def test_fake_embeddings_deterministic(self):
        """Test that fake embeddings are deterministic."""
        embeddings = DeterministicFakeEmbeddings(dimension=100)
        
        text = "troubleshooting system errors"
        vector1 = embeddings.embed_query(text)
        vector2 = embeddings.embed_query(text)
        
        # Should be identical
        assert vector1 == vector2
        assert len(vector1) == 100
    
    def test_fake_embeddings_similarity(self):
        """Test that similar texts get similar embeddings."""
        embeddings = DeterministicFakeEmbeddings(dimension=100)
        
        # Similar texts
        text1 = "troubleshooting system"
        text2 = "troubleshoot problems"
        
        # Different texts
        text3 = "maintenance procedures"
        
        vector1 = embeddings.embed_query(text1)
        vector2 = embeddings.embed_query(text2)
        vector3 = embeddings.embed_query(text3)
        
        # Calculate cosine similarity
        def cosine_similarity(v1, v2):
            dot_product = sum(a * b for a, b in zip(v1, v2))
            magnitude1 = sum(a * a for a in v1) ** 0.5
            magnitude2 = sum(b * b for b in v2) ** 0.5
            return dot_product / (magnitude1 * magnitude2) if magnitude1 > 0 and magnitude2 > 0 else 0
        
        sim_1_2 = cosine_similarity(vector1, vector2)
        sim_1_3 = cosine_similarity(vector1, vector3)
        
        # Similar texts should be more similar than different texts
        assert sim_1_2 > sim_1_3
    
    def test_vector_retriever_basic(self):
        """Test that vector retriever returns relevant documents."""
        retriever = FakeVectorRetriever()
        
        # Test troubleshooting query
        docs = retriever._get_relevant_documents("troubleshoot system errors")
        assert len(docs) > 0
        assert any("troubleshoot" in doc.page_content.lower() for doc in docs)
        
        # Test maintenance query
        docs = retriever._get_relevant_documents("maintenance procedures")
        assert len(docs) > 0
        assert any("maintenance" in doc.page_content.lower() for doc in docs)
    
    def test_vector_retriever_deterministic(self):
        """Test that vector retriever returns consistent results."""
        retriever = FakeVectorRetriever()
        
        query = "troubleshoot errors"
        docs1 = retriever._get_relevant_documents(query)
        docs2 = retriever._get_relevant_documents(query)
        
        # Should return same documents in same order
        assert len(docs1) == len(docs2)
        for doc1, doc2 in zip(docs1, docs2):
            assert doc1.page_content == doc2.page_content
            assert doc1.metadata == doc2.metadata
    
    def test_vector_retriever_custom_documents(self):
        """Test vector retriever with custom documents."""
        from langchain.schema import Document
        
        custom_docs = [
            Document(page_content="Custom test document about testing", metadata={"type": "test"}),
            Document(page_content="Another document about development", metadata={"type": "dev"})
        ]
        
        retriever = FakeVectorRetriever(documents=custom_docs)
        docs = retriever._get_relevant_documents("testing")
        
        assert len(docs) > 0
        assert any("test" in doc.page_content.lower() for doc in docs)
    
    def test_factory_functions(self):
        """Test the factory functions work correctly."""
        llm = create_test_llm()
        embeddings = create_test_embeddings()
        retriever = create_test_retriever()
        
        # Basic functionality test
        response = llm._call("test query")
        assert isinstance(response, str)
        assert len(response) > 0
        
        vector = embeddings.embed_query("test text")
        assert isinstance(vector, list)
        assert len(vector) > 0
        
        docs = retriever._get_relevant_documents("test query")
        assert isinstance(docs, list)
        assert len(docs) > 0
    
    def test_llm_callable_interface(self):
        """Test that LLM can be called like a function."""
        llm = DeterministicFakeLLM()
        
        # Test direct call
        response1 = llm("test query")
        response2 = llm._call("test query")
        
        assert response1 == response2
        
        # Test invoke method
        response3 = llm.invoke({"input": "test query"})
        assert isinstance(response3, str)
    
    def test_retriever_callable_interface(self):
        """Test that retriever can be called like a function."""
        retriever = FakeVectorRetriever()
        
        # Test direct call
        docs1 = retriever("test query")
        docs2 = retriever._get_relevant_documents("test query")
        
        assert len(docs1) == len(docs2)
        
        # Test invoke method
        docs3 = retriever.invoke({"input": "test query"})
        assert isinstance(docs3, list)
        assert len(docs3) > 0


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"]) 