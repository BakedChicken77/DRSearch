#!/usr/bin/env python3
"""
Quick demonstration of fake components for DRSearch backend testing.

This script shows how the fake LLM, embeddings, and retriever components work
without running the full test suite. Useful for development and debugging.

Usage:
    cd drsearch_backend
    poetry run python ../test_full_app/demo_fake_components.py
"""

import os
import sys
from pathlib import Path


def setup_basic_environment():
    """Set up minimal environment for component testing."""
    test_env = {
        "LOG_LEVEL": "INFO",
    }
    
    for key, value in test_env.items():
        os.environ[key] = value
    
    print("✓ Basic environment configured for component demo")


def run_component_demo():
    """Run a quick demonstration of the fake components."""
    print("\n🔧 Fake Components Demonstration")
    print("=" * 40)
    
    try:
        # Check if we're running from the backend directory
        current_dir = Path.cwd()
        if current_dir.name != "drsearch_backend":
            print("✗ This script should be run from the drsearch_backend directory")
            print("Usage: cd drsearch_backend && poetry run python ../test_full_app/demo_fake_components.py")
            return False
        
        # Add the test components directory to Python path
        test_components_dir = current_dir.parent / "test_full_app" / "backend"
        sys.path.insert(0, str(test_components_dir))
        
        # Import our fake components
        from fake_components import (
            DeterministicFakeLLM,
            DeterministicFakeEmbeddings,
            FakeVectorRetriever
        )
        
        # Demo fake LLM
        print("\n1. 🤖 Testing Fake LLM:")
        print("   Demonstrates deterministic responses based on query patterns")
        llm = DeterministicFakeLLM()
        
        test_queries = [
            "How to troubleshoot system errors?",
            "What are the maintenance procedures?", 
            "What is part number PN-123?",
            "How do I configure the system?",
            "What are the safety requirements?"
        ]
        
        for query in test_queries:
            response = llm._call(query)
            print(f"   Q: {query}")
            print(f"   A: {response[:80]}...")
            print()
        
        # Demo fake embeddings
        print("2. 🔢 Testing Fake Embeddings:")
        print("   Shows deterministic vector generation based on keywords")
        embeddings = DeterministicFakeEmbeddings(dimension=10)  # Small dimension for demo
        
        test_texts = [
            "troubleshooting guide", 
            "maintenance manual", 
            "part catalog",
            "safety procedures",
            "configuration settings"
        ]
        
        for text in test_texts:
            vector = embeddings.embed_query(text)
            print(f"   Text: '{text}'")
            print(f"   Vector: [{', '.join(f'{x:.3f}' for x in vector[:5])}...]")
            print()
        
        # Demo similarity between similar texts
        print("   Testing similarity between related texts:")
        vec1 = embeddings.embed_query("troubleshoot system")
        vec2 = embeddings.embed_query("troubleshooting guide")
        vec3 = embeddings.embed_query("maintenance check")
        
        # Calculate cosine similarity
        import numpy as np
        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        
        sim_12 = cosine_similarity(vec1, vec2)
        sim_13 = cosine_similarity(vec1, vec3)
        
        print(f"   Similarity 'troubleshoot system' vs 'troubleshooting guide': {sim_12:.3f}")
        print(f"   Similarity 'troubleshoot system' vs 'maintenance check': {sim_13:.3f}")
        print()
        
        # Demo test retriever
        print("3. 📚 Testing Vector Retriever:")
        print("   Shows document retrieval based on query similarity")
        retriever = FakeVectorRetriever()
        
        test_queries = [
            "troubleshoot errors", 
            "maintenance check", 
            "part information",
            "safety guidelines",
            "system configuration"
        ]
        
        for query in test_queries:
            docs = retriever._get_relevant_documents(query)
            print(f"   Query: '{query}'")
            print(f"   Retrieved {len(docs)} documents:")
            for i, doc in enumerate(docs[:3], 1):  # Show first 3 docs
                filename = doc.metadata.get('filename', 'unknown')
                content_preview = doc.page_content[:50].replace('\n', ' ')
                print(f"     {i}. {filename}: {content_preview}...")
            print()
        
        # Demo MultiQueryRetriever compatibility
        print("4. 🔍 Testing MultiQueryRetriever Compatibility:")
        print("   Shows how fake LLM handles multi-query generation patterns")
        
        multi_query_prompts = [
            "Generate multiple search queries for: troubleshooting network issues",
            "Create alternative questions for: system maintenance procedures",
            "Provide different phrasings for: part number lookup"
        ]
        
        for prompt in multi_query_prompts:
            response = llm._call(prompt)
            print(f"   Prompt: {prompt}")
            print(f"   Response: {response[:60]}...")
            print()
        
        print("✅ All fake components working correctly!")
        print("\n💡 Key Features Demonstrated:")
        print("   • Deterministic LLM responses based on query patterns")
        print("   • Keyword-based embedding vectors with similarity")
        print("   • Document retrieval with relevance scoring")
        print("   • MultiQueryRetriever compatibility")
        print("\n🎯 These components provide predictable behavior for testing")
        print("   while maintaining the same interfaces as production components.")
        
        return True
        
    except Exception as e:
        print(f"✗ Error in demo: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main demo script."""
    print("🎭 DRSearch Fake Components Demo")
    print("This script demonstrates the fake components used for testing")
    print("without running the full test suite.\n")
    
    # Setup minimal environment
    setup_basic_environment()
    
    # Run component demo
    if not run_component_demo():
        print("\n❌ Demo failed - check fake components installation")
        sys.exit(1)
    
    print("\n🎉 Demo completed successfully!")
    print("\nNext steps:")
    print("• Run 'poetry run python ../test_full_app/run_backend_e2e_tests.py' for full E2E tests")
    print("• Examine 'test_full_app/backend/fake_components.py' for implementation details")
    print("• Extend fake components for more complex test scenarios")


if __name__ == "__main__":
    main() 