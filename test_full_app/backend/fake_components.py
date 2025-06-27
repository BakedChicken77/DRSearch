"""
Fake LLM and Embedder components for deterministic backend API testing.

These components replace external AI services with predictable implementations
for reliable end-to-end testing of the drsearch_backend API.
"""

import time
import hashlib
import json
from typing import Dict, List, Iterator, Any, Optional, Union, AsyncIterator
from langchain_core.language_models.fake import FakeListLLM
from langchain.schema import BaseRetriever, Document, AIMessage, HumanMessage
from langchain_core.callbacks import (
    CallbackManagerForLLMRun,
    AsyncCallbackManagerForLLMRun,
)
from langchain_core.outputs import LLMResult, Generation


class DeterministicFakeLLM:
    """
    Enhanced fake LLM that provides deterministic responses based on input patterns.

    This LLM analyzes the input prompt and generates contextually appropriate responses
    for testing RAG pipelines, chat flows, and API contracts.

    This is a simple callable class that mimics the LLM interface without Pydantic restrictions.
    """

    def __init__(self, **kwargs):
        """Initialize the fake LLM with configurable response patterns."""
        # Response patterns for different query types
        self.response_patterns = {
            "troubleshoot": "To troubleshoot {issue}, follow these steps:\n1. Check connections\n2. Verify settings\n3. Restart system\n4. Contact support if needed",
            "maintenance": "For maintenance procedures:\n1. Power down the system\n2. Follow safety protocols\n3. Perform required checks\n4. Document completion",
            "what is": "Based on the documentation, {topic} is a {type} that {description}",
            "how to": "Here are the step-by-step instructions for {action}:\n1. Preparation\n2. Execution\n3. Verification\n4. Documentation",
            "error": "This error typically occurs when {cause}. To resolve:\n1. Check logs\n2. Verify configuration\n3. Apply fix\n4. Test resolution",
            "part number": "Part number {part_number} is used for {application}. Key specifications: {specs}",
            "default": "Based on the provided context and documentation, here is a comprehensive response addressing your question.",
        }

        # Chat context awareness
        self.chat_history_patterns = {
            "follow_up": "Following up on our previous discussion, ",
            "clarification": "To clarify the previous point, ",
            "continuation": "Continuing from where we left off, ",
        }

        # Keep track of call count for MultiQueryRetriever compatibility
        self.call_count = 0

    def _analyze_prompt(self, prompt: str, context: str = "") -> Dict[str, Any]:
        """Analyze the prompt to determine appropriate response pattern."""
        prompt_lower = prompt.lower()

        # Extract key information
        analysis = {
            "pattern_type": "default",
            "entities": [],
            "has_context": bool(context.strip()),
            "is_follow_up": any(
                word in prompt_lower
                for word in ["also", "additionally", "furthermore", "what about"]
            ),
        }

        # Determine response pattern
        for pattern, template in self.response_patterns.items():
            if pattern in prompt_lower:
                analysis["pattern_type"] = pattern
                break

        # Extract entities (part numbers, issues, etc.)
        words = prompt.split()
        for i, word in enumerate(words):
            if word.upper().startswith("PN-") or "part" in word.lower():
                analysis["entities"].append({"type": "part_number", "value": word})
            elif "error" in word.lower() or "issue" in word.lower():
                if i < len(words) - 1:
                    analysis["entities"].append(
                        {"type": "issue", "value": words[i + 1]}
                    )

        return analysis

    def _generate_response(
        self, prompt: str, context: str = "", chat_history: List = None
    ) -> str:
        """Generate a deterministic response based on prompt analysis."""
        analysis = self._analyze_prompt(prompt, context)
        pattern_type = analysis["pattern_type"]

        # Get base response template
        template = self.response_patterns[pattern_type]

        # Add chat history context if present
        response_prefix = ""
        if chat_history and len(chat_history) > 0:
            if analysis["is_follow_up"]:
                response_prefix = self.chat_history_patterns["follow_up"]

        # Fill in template variables
        response = template
        for entity in analysis["entities"]:
            placeholder = "{" + entity["type"] + "}"
            if placeholder in response:
                response = response.replace(placeholder, entity["value"])

        # Fill remaining placeholders with generic content
        response = response.replace("{issue}", "the reported issue")
        response = response.replace("{topic}", "the requested topic")
        response = response.replace("{type}", "component")
        response = response.replace("{description}", "performs specific functions")
        response = response.replace("{action}", "the requested procedure")
        response = response.replace("{cause}", "configuration issues")
        response = response.replace("{part_number}", "PN-XXXX")
        response = response.replace("{application}", "system operations")
        response = response.replace("{specs}", "standard specifications")

        # Add context information if available
        if context.strip():
            response = f"{response_prefix}{response}\n\nThis information is based on the following documentation:\n{context[:200]}{'...' if len(context) > 200 else ''}"

        return response

    def invoke(self, input_data: Dict[str, Any], **kwargs) -> str:
        """LangChain-style invoke method."""
        if isinstance(input_data, dict):
            prompt = input_data.get("text", input_data.get("input", str(input_data)))
        else:
            prompt = str(input_data)
        return self._call(prompt, **kwargs)

    def _call(
        self, prompt: Any, stop: Optional[List[str]] = None, **kwargs: Any
    ) -> str:
        """Generate a complete response synchronously."""
        self.call_count += 1

        # Convert ChatPromptValue or message sequences to text
        if not isinstance(prompt, str):
            if hasattr(prompt, "to_string"):
                prompt = prompt.to_string()
            elif hasattr(prompt, "messages"):
                prompt = "\n".join(
                    getattr(m, "content", str(m)) for m in prompt.messages
                )
            else:
                prompt = str(prompt)

        # Check if this is a MultiQueryRetriever call (typically contains specific patterns)
        if (
            "generate" in prompt.lower() and "question" in prompt.lower()
        ) or "similar questions" in prompt.lower():
            # This is likely a MultiQueryRetriever call, return multiple queries
            return "How to troubleshoot the system?\nWhat are common error solutions?\nSystem troubleshooting steps?"

        # Otherwise generate a contextual response
        context = kwargs.get("context", "")
        chat_history = kwargs.get("chat_history", [])
        return self._generate_response(prompt, context, chat_history)

    def __call__(self, *args, **kwargs):
        """Make the class callable like a function."""
        if args:
            return self._call(args[0], **kwargs)
        return self._call("", **kwargs)


class DeterministicFakeEmbeddings:
    """
    Fake embeddings that generate deterministic vectors based on text content.

    This ensures that similar texts get similar embeddings for consistent
    retrieval behavior in tests.
    """

    def __init__(self, dimension: int = 1536):
        """
        Initialize fake embeddings.

        Args:
            dimension: Vector dimension (default matches OpenAI embeddings)
        """
        self.dimension = dimension

        # Predefined keywords and their base vectors
        self.keyword_vectors = {
            "troubleshoot": [0.8, 0.2, 0.1] + [0.0] * (dimension - 3),
            "maintenance": [0.2, 0.8, 0.1] + [0.0] * (dimension - 3),
            "error": [0.9, 0.1, 0.0] + [0.0] * (dimension - 3),
            "part": [0.1, 0.1, 0.8] + [0.0] * (dimension - 3),
            "procedure": [0.3, 0.6, 0.1] + [0.0] * (dimension - 3),
            "system": [0.4, 0.4, 0.2] + [0.0] * (dimension - 3),
            "test": [0.7, 0.3, 0.0] + [0.0] * (dimension - 3),
            "testing": [0.7, 0.3, 0.0] + [0.0] * (dimension - 3),
            "document": [0.2, 0.2, 0.6] + [0.0] * (dimension - 3),
            "development": [0.1, 0.7, 0.2] + [0.0] * (dimension - 3),
            "custom": [0.5, 0.2, 0.3] + [0.0] * (dimension - 3),
            "guide": [0.3, 0.5, 0.2] + [0.0] * (dimension - 3),
            "manual": [0.2, 0.7, 0.1] + [0.0] * (dimension - 3),
            "diagnostic": [0.8, 0.1, 0.1] + [0.0] * (dimension - 3),
            "operation": [0.4, 0.5, 0.1] + [0.0] * (dimension - 3),
        }

    def _text_to_vector(self, text: str) -> List[float]:
        """Convert text to a deterministic embedding vector."""
        text_lower = text.lower()

        # Start with base vector
        vector = [0.0] * self.dimension

        # Add contributions from keywords
        total_weight = 0.0
        for keyword, base_vector in self.keyword_vectors.items():
            if keyword in text_lower:
                weight = text_lower.count(keyword) / len(text_lower.split())
                total_weight += weight
                for i in range(min(len(base_vector), self.dimension)):
                    vector[i] += weight * base_vector[i]

        # Add hash-based components for uniqueness
        text_hash = hashlib.md5(text.encode()).hexdigest()
        for i in range(min(8, self.dimension - len(self.keyword_vectors) * 3)):
            hash_val = int(text_hash[i * 4 : (i + 1) * 4], 16) / 65535.0 - 0.5
            vector[len(self.keyword_vectors) * 3 + i] = hash_val * 0.1

        # Normalize vector
        magnitude = sum(x * x for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]

        return vector

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        return self._text_to_vector(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents."""
        return [self._text_to_vector(text) for text in texts]


class FakeVectorRetriever:
    """
    In-memory vector retriever with predefined test documents.

    This retriever provides deterministic document retrieval for testing
    the RAG pipeline without external vector stores.

    This is a simple class that mimics the retriever interface without Pydantic restrictions.
    """

    def __init__(self, documents: Optional[List[Document]] = None):
        """
        Initialize with test documents.

        Args:
            documents: List of test documents. If None, uses default test set.
        """
        self.embeddings = DeterministicFakeEmbeddings()
        self.documents = documents or self._create_default_documents()

        # Pre-compute document embeddings
        self.document_embeddings = {}
        for i, doc in enumerate(self.documents):
            self.document_embeddings[i] = self.embeddings.embed_documents(
                [doc.page_content]
            )[0]

    def _create_default_documents(self) -> List[Document]:
        """Create a default set of test documents."""
        return [
            Document(
                page_content="Troubleshooting procedures for system errors. Check connections, verify configuration, restart services, and contact support if issues persist.",
                metadata={
                    "filename": "troubleshooting_guide.pdf",
                    "part_number": "PN-001",
                    "section": "error_handling",
                },
            ),
            Document(
                page_content="Maintenance procedures require proper safety protocols. Power down systems, follow checklists, perform inspections, and document all work.",
                metadata={
                    "filename": "maintenance_manual.pdf",
                    "part_number": "PN-002",
                    "section": "routine_maintenance",
                },
            ),
            Document(
                page_content="Part number PN-003 is a critical component for system operation. Regular inspection and replacement following manufacturer guidelines is essential.",
                metadata={
                    "filename": "parts_catalog.pdf",
                    "part_number": "PN-003",
                    "section": "components",
                },
            ),
            Document(
                page_content="Error codes and diagnostic procedures help identify system issues. Reference the error code table and follow step-by-step troubleshooting.",
                metadata={
                    "filename": "diagnostic_manual.pdf",
                    "part_number": "PN-004",
                    "section": "diagnostics",
                },
            ),
            Document(
                page_content="System procedures outline proper operation sequences. Follow all steps in order and verify completion before proceeding to next phase.",
                metadata={
                    "filename": "operation_manual.pdf",
                    "part_number": "PN-005",
                    "section": "procedures",
                },
            ),
        ]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def get_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        """Retrieve documents relevant to the query."""
        return self._get_relevant_documents(query, **kwargs)

    def invoke(self, input_data: Dict[str, Any], **kwargs) -> List[Document]:
        """LangChain-style invoke method."""
        if isinstance(input_data, dict):
            query = input_data.get("query", input_data.get("input", str(input_data)))
        else:
            query = str(input_data)
        return self._get_relevant_documents(query, **kwargs)

    def _get_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        """Retrieve documents relevant to the query."""
        query_embedding = self.embeddings.embed_query(query)

        # Calculate similarities
        similarities = []
        for i, doc_embedding in self.document_embeddings.items():
            similarity = self._cosine_similarity(query_embedding, doc_embedding)
            similarities.append((similarity, i))

        # Sort by similarity and return top documents
        similarities.sort(reverse=True, key=lambda x: x[0])

        # Return top 3 documents by default
        top_docs = []
        for similarity, doc_idx in similarities[:3]:
            if similarity > 0.1:  # Minimum similarity threshold
                top_docs.append(self.documents[doc_idx])

        return (
            top_docs if top_docs else [self.documents[0]]
        )  # Always return at least one document

    async def aget_relevant_documents(self, query: str, **kwargs) -> List[Document]:
        """Async version of document retrieval."""
        return self._get_relevant_documents(query, **kwargs)

    def __call__(self, *args, **kwargs):
        """Make the class callable like a function."""
        if args:
            return self._get_relevant_documents(args[0], **kwargs)
        return self._get_relevant_documents("", **kwargs)


# Factory functions for easy integration
def create_test_llm(**kwargs) -> DeterministicFakeLLM:
    """Create a configured fake LLM for testing."""
    return DeterministicFakeLLM(**kwargs)


def create_test_embeddings(**kwargs) -> DeterministicFakeEmbeddings:
    """Create a configured fake embeddings model for testing."""
    return DeterministicFakeEmbeddings(**kwargs)


def create_test_retriever(
    documents: Optional[List[Document]] = None,
) -> FakeVectorRetriever:
    """Create a configured test retriever with optional custom documents."""
    return FakeVectorRetriever(documents)
