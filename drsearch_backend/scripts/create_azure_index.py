"""Create or update an Azure AI Search index for DRSearch."""

from __future__ import annotations

import logging
import os
from typing import Sequence

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceExistsError
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchField,
    SearchFieldDataType,
    SearchableField,
    VectorSearch,
    VectorSearchAlgorithmConfiguration,
    VectorSearchProfile,
)

from app.chain.embeddings import EmbeddingFactory


logger = logging.getLogger(__name__)


def _build_fields(dimension: int) -> Sequence[SearchField | SimpleField]:
    """Return the list of fields for the index."""
    return [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchableField(name="file_path", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchableField(name="filename", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchableField(name="url", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchableField(name="text_as_html", type=SearchFieldDataType.String, retrievable=True),
        SearchableField(name="source", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchableField(name="title", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchableField(name="file_directory", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=dimension,
            vector_search_profile_name="drsearch-vectors",
        ),
    ]


def _build_index(index_name: str, dimension: int) -> SearchIndex:
    return SearchIndex(
        name=index_name,
        fields=list(_build_fields(dimension)),
        vector_search=VectorSearch(
            algorithms=[
                VectorSearchAlgorithmConfiguration(name="drsearch-hnsw", kind="hnsw")
            ],
            profiles=[
                VectorSearchProfile(
                    name="drsearch-vectors", algorithm_configuration_name="drsearch-hnsw"
                )
            ],
        ),
    )


def create_index_if_missing(endpoint: str, key: str, index_name: str, dimension: int) -> SearchClient:
    """Create the Azure Search index if it does not exist and return a search client."""
    credential = AzureKeyCredential(key)
    iclient = SearchIndexClient(endpoint=endpoint, credential=credential)

    try:
        iclient.create_index(_build_index(index_name, dimension))
        logger.info("Index '%s' created", index_name)
    except ResourceExistsError:
        logger.info("Index '%s' already exists", index_name)

    return SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)


def load_sample_documents(client: SearchClient, dimension: int) -> None:
    """Upload basic sample documents for validation."""
    embedder = EmbeddingFactory.get()
    content = "Sample document for DRSearch"
    vector = embedder.embed_query(content)

    docs = [
        {
            "id": "1",
            "content": content,
            "file_path": "samples/doc1.txt",
            "filename": "doc1.txt",
            "url": "https://example.com/doc1.txt",
            "text_as_html": "<p>Sample document for DRSearch</p>",
            "source": "example",
            "title": "Sample Document",
            "file_directory": "samples",
            "content_vector": vector,
        }
    ]

    result = client.upload_documents(docs)
    if not all(r.succeeded for r in result):
        raise RuntimeError(f"Failed to upload documents: {result}")
    logger.info("Uploaded %s sample document(s)", len(docs))


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    key = os.environ.get("AZURE_SEARCH_KEY")
    if not endpoint or not key:
        raise EnvironmentError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY must be set")

    index_name = os.environ.get("AZURE_SEARCH_INDEX", "drsearch-index")
    dimension = int(os.environ.get("AZURE_VECTOR_DIMENSION", "1536"))

    client = create_index_if_missing(endpoint, key, index_name, dimension)
    load_sample_documents(client, dimension)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - script entry point
        logger.error("Failed to create index: %s", exc)
        raise
