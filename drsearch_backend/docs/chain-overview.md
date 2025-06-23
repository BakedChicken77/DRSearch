# DRSearch Chain Module Overview

This document describes in detail how the `app/chain` package orchestrates the Retrieval Augmented Generation (RAG) pipeline within the DRSearch backend. It summarises the components, data flow and execution sequence observed in the source code.

**Update:** the legacy LangChain graph has been replaced by an OpenAI based RAG Search Agent defined in `app/search_agent`. The agent relies on tools for similarity, keyword and hybrid search against the pgvector database and handles document filtering and `top_k` parameters itself. The `/chat` route still uses LangServe but now delegates to this agent.

## Key Components

- **ChatEngine (`engine.py`)** – Builds and configures LangChain runnable chains for answering user questions. It initialises the language model, optional retriever and formatting logic.
- **RetrieverFactory (`retriever.py`)** – Creates `langchain` retrievers backed by a vector store (Weaviate or PgVector) based on `INDEX_CONFIG` and `chain_config` settings.
- **DocumentFormatter (`formatter.py`)** – Post‑processes retrieved documents: deduplicates, optionally reorders long contexts and enriches each document with a UNC file path when a mapping is available.
- **HistorySerializer (`history.py`)** – Converts incoming chat history dictionaries into LangChain message objects so the model receives previous human/AI messages in the correct format.
- **PartNumberMapping (`mapping.py`)** – Lazy loader for CSV files containing part‑number to UNC path mappings. Used by `DocumentFormatter`.
- **EmbeddingFactory (`embeddings.py`)** – Provides a singleton instance of the Azure OpenAI embedding model used by vector stores.
- **API helpers (`api.py`)** – Caches `ChatEngine` instances and exposes `get_answer_chain` / `answer_chain` for API routes and the CLI.
- **CLI (`cli.py`)** – Command‑line tool to run the chain interactively or to answer a single question outside of FastAPI.
- **Custom exception (`exceptions.py`)** – Defines `ConfigurationError` for missing or malformed index configuration.

## Data Flow and Process Sequence

1. **Engine Selection**
   - Calls to `get_answer_chain()` (via API or CLI) resolve an index name and desired number of retrieved documents. `_engine_for()` maintains a cache keyed by `(index_name, num_docs)` to reuse `ChatEngine` instances.

2. **ChatEngine Initialisation**
   - On first use, `ChatEngine` loads index-specific settings from `INDEX_CONFIG`.
   - It also creates a `PartNumberMapping` instance pointing at a CSV file when provided by the configuration.
   - `_init_llm()` constructs an `AzureChatOpenAI` model with environment parameters and streaming enabled.
   - `_build_answer_chain()` assembles the LangChain graph based on whether retrieval is enabled (`RAG_ON`) and whether the index was recognised.

3. **Retrieval Setup** (when RAG is active and index config is valid)
   - `RetrieverFactory.build()` obtains a retriever from the configured vector store. A simple boolean filter (`use4RAG == True`) is applied to exclude irrelevant documents.
   - The retriever is wrapped with `MultiQueryRetriever` using a question decomposer prompt from `INDEX_CONFIG`. This expands the user query into multiple search queries handled by the vector database.
   - `DocumentFormatter` is prepared to convert retrieved documents into `<doc/>` XML fragments. It deduplicates results and optionally reorders them for better context.

4. **Chain Construction**
   - A `ChatPromptTemplate` with system, history and user message placeholders is created. The system prompt is chosen based on the index configuration or falls back to a chatbot-only prompt.
   - If retrieval is active, `_build_retriever_chain()` creates a branchable retriever pipeline:
     1. The user question is condensed using the `REPHRASE_TEMPLATE` to handle follow-up questions.
     2. The retriever executes the vector search.
     3. `_modify_docs()` enriches each `Document` with UNC paths using `PartNumberMapping` data.
     4. A `RunnableBranch` selects the appropriate path depending on whether chat history exists.
   - The outputs are mapped to a context dictionary (`{"context", "question", "chat_history"}`) before reaching the final model call.
   - The final step is `prompt | llm | StrOutputParser()` with streaming enabled.

5. **Answer Generation**
   - Incoming inputs (question, chat history, index name) first go through `HistorySerializer` to convert raw history records into message objects.
   - The retriever (if enabled) fetches documents which `DocumentFormatter` serialises as XML. These become the `context` variable for the model.
   - The language model receives the full prompt and produces the answer string, which is returned to the caller (API route or CLI).

6. **CLI Interaction**
   - Running `python -m app.chain.cli` provides a REPL. The engine is built for the desired index, and questions are repeatedly passed to the chain. History is accumulated locally until the user exits.

## Notable Patterns

- **Caching** – `ChatEngine` instances are memoised in `_engine_cache` to avoid reinitialising expensive components for repeated calls with the same settings.
- **Environment‑Driven Configuration** – `chain_config.py` loads environment variables at import time, controlling aspects such as `RAG_ON`, vector backend, and authentication. This design ensures consistent behaviour whether running via FastAPI, the CLI or unit tests.
- **Lazy Resource Creation** – `EmbeddingFactory` and `PartNumberMapping` only create heavy objects when first accessed, minimising startup time.
- **Branchable Retriever Chain** – `_build_retriever_chain()` uses `RunnableBranch` so follow-up questions with existing history are rephrased, while standalone questions skip that step.
- **Document Reordering** – When RAG is enabled, `LongContextReorder` improves context windows by reordering retrieved chunks before feeding them to the model.

The chain module thus orchestrates the entire question‑answering pipeline, from environment setup through retrieval and prompt construction to the final language‑model call.
