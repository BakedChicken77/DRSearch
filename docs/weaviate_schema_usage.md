# Weaviate Schema Reconstruction

This document summarizes how the backend retrieves data from Weaviate and maps those queries to the schema defined in `weaviate_schema.json`.

## Retrieval Code References

### Filter on `use4RAG`
Lines 24‑41 of `app/chain/retriever.py` build a filter so only documents where `use4RAG` is `True` are returned:
```python
                raise ConfigurationError(
                    f"Index '{index_name}' not defined in INDEX_CONFIG"
                )
    
            store = VectorStoreFactory.create(index_name)
    
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

### Vector store configuration
Lines 19‑32 of `app/vectorstores/weaviate_store.py` show how the `langchain` Weaviate store is created. The `index_key` and list of additional `attributes` come from `INDEX_CONFIG`:
```python
        def __init__(self, index_name: str) -> None:
            cfg = INDEX_CONFIG[index_name]
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

### Retriever construction
`ChatEngine` calls `RetrieverFactory.build` and wraps the retriever with `MultiQueryRetriever` if retrieval is enabled. Lines 103‑140 illustrate this:
```python
            if RAG_ON and not getattr(self, "_unknown_index", False):
                try:
                    retriever = RetrieverFactory.build(self._index_name)
                    raw_retriever = RetrieverFactory.build(self._index_name)
                    format_docs_fn = DocumentFormatter(self._mapping)
                    enable_retrieval = True
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to initialise retriever – running without RAG: %s",
                        exc,
                    )
                    response_template = System_Prompts.RESPONSE_TEMPLATE_CHATBOT
                    enable_retrieval = False
            elif RAG_ON and getattr(self, "_unknown_index", False):
                logger.warning(
                    "Index '%s' not configured – retrieval disabled", self._index_name
                )
                response_template = System_Prompts.RESPONSE_TEMPLATE_CHATBOT
                enable_retrieval = False
            else:
                logger.info("Running in chatbot-only mode – retrieval disabled")
    
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", response_template),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{question}"),
                ]
            )
    
            if enable_retrieval and raw_retriever is not None:
                # decomposer_prompt = PromptTemplate.from_template(System_Prompts.REPHRASE_TEMPLATE)
                retriever = MultiQueryRetriever.from_llm(
                    retriever=raw_retriever,
                    llm=self._llm,
                    include_original=True,
                    prompt=self._cfg["DECOMPOSER"],
                )
```

### Index configuration
`INDEX_CONFIG` defines the available classes, which attributes are retrieved and which property stores the text content. Example entries are shown below (lines 4‑90 of `app/index_config.py`):
```python
    # Configuration dictionary for index names, attributes, and response templates
    INDEX_CONFIG = {
        "SEPs_F_T_C_W_A_V": {
            "attributes": ["file_path", "filename", "url", "text_as_html"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_SEPS,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
            "PN_TO_FILE_MAPPING": None
        },
        "SEPs_F_T_C_W_A_V_Summaries": {
            "attributes": ["file_path", "filename", "url", "text_as_html"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_SEPS,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
            "PN_TO_FILE_MAPPING": None
        },
        "SEPs_F_T_C_W_A_V_Summaries_5000": {
            "attributes": ["file_path", "filename", "url", "text_as_html"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_SEPS,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
            "PN_TO_FILE_MAPPING": None
        },
        "LangChain_agent_docs": {
            "attributes": ["source", "title"],
            "index_key": "text",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_LANGCHAIN,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
            "PN_TO_FILE_MAPPING": None
        },
        "AZURE_10000MaxChunk": {
            "attributes": ["file_directory", "filename"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_AZURE,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
            "PN_TO_FILE_MAPPING": None
        },
        "WEAVIATE_DOCS": {
            "attributes": ["file_directory", "filename"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_WEAVIATE,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
            "PN_TO_FILE_MAPPING": None
        },
        "JACSKE_HDD_GPT": {
            "attributes": ["file_directory", "filename"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_JAC_SKE,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
            "PN_TO_FILE_MAPPING": None
        },
        "JACSKE_Program": {
            "attributes": ["file_path", "filename", "url", "text_as_html"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_JAC_SKE_PROGRAM_FOR_TECHS,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER_JACSKE,
            "PN_TO_FILE_MAPPING": 'JACSKE_PROD_DEPLOY.csv'
        },
        "test20240712": {
            "attributes": ["file_path", "filename", "url", "text_as_html"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_JAC_SKE_PROGRAM,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
            "PN_TO_FILE_MAPPING": None
        },
        "Injected_URL3": {
            "attributes": ["file_path", "url"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_SEPS,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER2,
            "PN_TO_FILE_MAPPING": None
        },
        "HFSS_GUIDE_20240813": {
            "attributes": ["file_path", "filename", "url", "text_as_html"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_HFSS,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER_HFSS,
            "PN_TO_FILE_MAPPING": None
        },
        "Adacstest20250205": {
            "attributes": ["file_path", "filename", "url", "text_as_html"],
            "index_key": "page_content",
            "response_template": System_Prompts.RESPONSE_TEMPLATE_ADACS_TECH,
            "DECOMPOSER": System_Prompts.QUESTION_DECOMPOSER_ADACS_TECH,
            "PN_TO_FILE_MAPPING": "ADACS_TECH.csv"
        }
    }
```

## Schema Mapping

- **Content field** – each class has either `page_content` or `text` as the `text_key` used when `WeaviateVectorStore` is instantiated.
- **Metadata fields** – attributes listed for each class in `INDEX_CONFIG` are included in the schema so their values can be returned as metadata.
