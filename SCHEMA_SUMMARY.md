# Weaviate Schema Reconstruction

This file summarises how the backend queries Weaviate and documents the required schema.

## Retrieval logic

- `WeaviateVectorStore` instantiates a LangChain Weaviate store using a class name from `INDEX_CONFIG`. The text field is configured via `index_key` and metadata fields via `attributes`:

```python
    client = weaviate.Client(
        url=chain_config._WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(api_key=chain_config._WEAVIATE_API_KEY),
    )
    self._store = LangchainWeaviate(
        client=client,
        index_name=index_name,
        text_key=cfg["index_key"],
        embedding=EmbeddingFactory.get(),
        by_text=False,
        attributes=cfg["attributes"],
    )
```
(*app/vectorstores/weaviate_store.py*)

- `RetrieverFactory` converts the vector store into a retriever. A where filter ensures only documents where `use4RAG` is `True` are searched:

```python
    filter_rag_only = {
        "operator": "Equal",
        "path": ["use4RAG"],
        "valueBoolean": True,
    }
    return store.as_retriever(
        search_kwargs={
            "k": chain_config._NUMBER_OF_DOCS_RETRIEVED,
            "where_filter": filter_rag_only,
        }
    )
```
(*app/chain/retriever.py*)

## Index configuration

`INDEX_CONFIG` defines the available class names, their text key and which metadata attributes are requested. Example:

```python
"SEPs_F_T_C_W_A_V": {
    "attributes": ["file_path", "filename", "url", "text_as_html"],
    "index_key": "page_content",
    ...
}
```
(*app/index_config.py*)

All other class definitions follow the same pattern with varying attribute lists and either `page_content` or `text` as the text field.

## Metadata usage

When formatting retrieved documents the application reads the `filename` field and may inject `file_path` if a mapping exists:

```python
filename = doc.metadata.get("filename", "Unknown part number")
if self._mapping and filename in self._mapping:
    doc.metadata["file_path"] = self._mapping[filename]
```
(*app/chain/formatter.py*)

No other metadata fields are accessed directly in the backend.

## Required schema elements

- A boolean field `use4RAG` filterable for retrieval.
- Text field given by `index_key` (`page_content` or `text`) used for vector similarity search.
- Metadata fields listed under `attributes` for each class.

The schema file `weaviate_schema.json` contains one class definition per index using the properties above. Every class is configured with `vectorizer: "none"` to match the external embedding logic and uses a cosine HNSW vector index.
