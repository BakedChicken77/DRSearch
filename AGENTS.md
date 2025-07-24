# DRSearch Project Guide for Codex

## Project Overview

DRSearch is a full-stack search and chatbot application combining a Next.js frontend with a FastAPI backend. The system provides a **Retrieval-Augmented Generation (RAG)** chatbot that can answer questions using both an indexed document knowledge base and direct responses. The backend (referred to as **DRSearch_LG**, "LangGraph" backend) integrates **LangChain/LangGraph** for AI reasoning and uses a PostgreSQL database with the **PGVector** extension for vector similarity search. The frontend is a React (Next.js 13) application for user interaction, while the backend handles AI logic, vector retrieval, and response streaming.

## Architecture and Components

- **Frontend (drsearch_frontend)** – A Next.js 13 React application (TypeScript) with Chakra UI for styling. It communicates with the backend via REST endpoints and Server-Sent Events for streaming responses.
- **Backend (drsearch_lg)** – A FastAPI application (Python) that implements the chatbot agent using LangChain/LangGraph. It provides API endpoints for querying the AI agent (`/invoke`, `/stream`), retrieving chat history, and logging feedback. 
- **Database (PostgreSQL + PGVector)** – Stores vector embeddings of documents for retrieval. The backend uses PGVector to perform similarity search on indexed documents. Traditional PostgreSQL tables may also be used for logging or record management (if configured).

**Design Patterns:** The backend’s AI logic is organized as a **stateful graph** (via LangGraph) that models the conversational workflow. User queries pass through a series of nodes: selecting data source, decomposing questions, retrieving relevant documents from the vector store, and generating answers with an LLM. The backend streams out partial results (tokens and status updates) to the frontend, which separates them into channels (response tokens, status messages, source documents) for a smooth UI experience. Authentication is supported via Azure AD JWT tokens or a static API key, and can be toggled on or off as needed.

## Build & Setup

### Backend Setup

1. **Install Dependencies:** The backend uses Poetry for dependency management. In the `drsearch_lg` directory, install the Python dependencies:
   ```bash
   cd drsearch_lg
   poetry install --all-extras --no-root


2. **Environment Configuration:** Copy the example environment file and adjust settings:

   ```bash
   cp .example.env .env
   # Open .env and edit configuration (database URLs, API keys, etc.)
   ```

   Key settings include `PGVECTOR_URL` for the database, `AI_PROVIDER` and API keys for OpenAI or Azure, and `AUTH_ENABLED`/`AUTH_SECRET` for authentication mode. By default, `USE_FAKE_MODEL` can be set to `"true"` to use a fake local model for testing (no external API calls).

3. **Run the Server:** Launch the FastAPI server (for example, using Uvicorn):

   ```bash
   uvicorn drsearch_lg.service.service:app --reload --port 8011
   ```

   This will start the API on port 8011 (as referenced by the frontend).

### Frontend Setup

1. **Install Dependencies:** In the `drsearch_frontend` directory, install Node.js packages (Yarn is used for this project):

   ```bash
   cd drsearch_frontend
   yarn install
   ```
2. **Environment Configuration:** Ensure the frontend `.env.local` (if any) is configured to point to the backend API URL (e.g., `NEXT_PUBLIC_API_URL="http://localhost:8011"` for local dev).
3. **Run the Frontend:** Start the Next.js development server:

   ```bash
   yarn dev
   ```

   The app will run on [http://localhost:3000](http://localhost:3000) by default.

## Testing Instructions

### Backend Testing

* **Run All Tests with Coverage:** From `drsearch_lg` directory, use Poetry to run pytest:

  ```bash
  cd drsearch_lg
  poetry run pytest --cov=app --cov-report=term-missing -q
  ```

  This executes all unit tests and reports coverage, focusing on the `app` package.
* **Run Specific Tests:** You can target a single test file or test case:

  ```bash
  poetry run pytest tests/path/to/test_file.py -v
  ```

  The backend tests use `pytest-asyncio` for async FastAPI endpoints and include fixtures for mocking AI providers (via `USE_FAKE_MODEL` and dummy embeddings).

### Frontend Testing

* **Linting:** Run ESLint to catch syntax and style issues:

  ```bash
  cd drsearch_frontend
  yarn lint
  ```
* **Formatting:** Ensure code is formatted with Prettier:

  ```bash
  yarn format
  ```
* **Unit Tests:** Run the frontend’s Jest tests with coverage:

  ```bash
  cd drsearch_frontend
  yarn test --coverage
  ```

  This will execute React component and utility tests. The frontend uses MSW (Mock Service Worker) in tests to simulate API responses from the backend.

## Development Workflow

### Backend Development

1. Make changes in the Python backend code under `drsearch_lg/` (for example, modifying agent logic in `agents/` or API behavior in `service/`).
2. Run the backend test suite (`pytest`) to ensure your changes do not break existing functionality. Focus on relevant test files under `drsearch_lg/tests/`.
3. Follow PEP 8 style guidelines. Use **Black** and **isort** for automatic formatting and import sorting (these are included in development dependencies).
4. Include type annotations for all functions and data models. The project uses Pydantic v2 models (with type validation) and expects type-safe code.
5. If adding new dependencies or environment variables, update `pyproject.toml` (for dependencies) and the example env file `.example.env` accordingly.

### Frontend Development

1. Modify or add React components and hooks in the `drsearch_frontend/app` directory (or subdirectories like `components/`, `utils/`, etc.).
2. Maintain the established component structure and naming conventions. UI components use Chakra UI for consistent styling.
3. Run the development server (`yarn dev`) to manually test changes in the browser. Use browser dev tools and React DevTools for debugging UI state.
4. Keep TypeScript types up to date: define interface/type for component props and API responses. The project is strict about type-checking.
5. Before committing, format with Prettier and ensure `yarn lint` passes. Fix any lint or type errors to keep CI checks happy.

## Code Structure

The repository is organized into frontend and backend directories, each with a clear responsibility. Below is the high-level structure focusing on the backend (DRSearch\_LG) and key frontend files:

### Backend (drsearch\_lg)

* **`app/`** – FastAPI application factory and configuration.

  * `app/core/config.py`: Defines the configuration via Pydantic BaseSettings (reads from `.env`). This includes settings for debug mode, CORS, auth, database URLs, and AI provider keys.
  * `app/auth/middleware.py`: Authentication middleware for Azure AD JWTs. It intercepts requests when `auth_enabled=True`, validates JWTs from Azure AD, and populates `request.state.user`. Also supports a whitelist of open endpoints and bypasses auth in dev mode.
  * `app/auth/jwt.py`: Helper for JWT validation (decoding and verifying tokens using JWKS). Raises `TokenValidationError` if the token is invalid or expired.
  * `app/middleware/logging.py`: Logging middleware to record incoming requests and outgoing responses. Also includes `StreamingLogMiddleware` to log streaming events for debugging. Logging behavior (JSON vs text, levels, etc.) is configured via environment variables.
  * `app/logging/config.py`: Sets up Python logging formatters and handlers based on settings (e.g., output to file in JSON format or console).
  * **Purpose:** The `app` package initializes the FastAPI `app` with all middleware (CORS, logging, auth) and provides the `create_app()` factory and `build_router()` function to attach authenticated routes.

* **`agents/`** – AI agent definitions using LangGraph (state machine for the chatbot).

  * `agents/agents.py`: Registers available agents in a dictionary. Currently defines the default `"rag_chatbot"` agent by compiling its graph.
  * `agents/rag_chatbot.py`: Constructs the RAG (Retrieval-Augmented Generation) chatbot agent. It loads environment (dotenv), ensures a fake model can be used if configured, and defines `create_graph()` which builds and compiles the LangGraph workflow.
  * `agents/rag_chatbot_components/`: Components of the RAG chatbot agent broken into multiple modules:

    * `graph_builder.py`: Assembles the `StateGraph` by adding nodes and conditional edges defining the chatbot’s reasoning flow (select index, decompose question, retrieve docs, grade relevance, generate answer, etc.).
    * `nodes.py`: Implements the logic of each node in the graph (functions such as `select_index`, `decompose_question`, `retrieve`, `generate`, etc.). Also includes decision functions for branching (e.g., `route_question`, `decide_to_generate`) and initialization of global models.
    * `model_utils.py`: Utilities to initialize AI models and vector stores. Provides `get_chat_model()` and `get_generate_chat_model()` to load either Azure or OpenAI chat models (or a local fake model), `get_embeddings_model()` for embedding generation, and `get_retriever()` which creates a PGVectorStore wrapper for a given index name.
    * `types.py`: Defines `TypedDict` schemas for the agent’s state (e.g. `GraphState` structure which includes fields like messages, question, documents, candidate\_answer, etc., and `ComponentQuestionState` for sub-question retrieval tasks).
    * `constants.py`: Defines constant values (like number of questions to decompose into, number of docs to retrieve, environment keys).
    * `utils.py`: Helper functions for formatting or filtering data (e.g., `format_docs()` to format retrieved docs into prompt context, `remove_duplicates()` to deduplicate docs, `create_status_message()` to tag status updates).
  * **Purpose:** The `agents` module composes the chatbot’s reasoning chain and exposes it as a **CompiledStateGraph**. This is the brain of the application that processes user queries via a sequence of steps (see **Agent Workflow** below).

* **`service/`** – FastAPI API routes and request handlers.

  * `service/service.py`: Defines the API router and endpoints. It creates the FastAPI `app` via `create_app()`, then attaches an APIRouter with endpoints:

    * `POST /{agent_id}/invoke` and `/invoke`: Process a one-shot query (returns a final answer as JSON).
    * `POST /{agent_id}/stream` and `/stream`: Process a query with streaming response (SSE), yielding tokens and intermediate messages.
    * `POST /feedback`: Record user feedback (rating) for a given run, forwarding it to LangChain’s LangSmith logging if configured.
    * `POST /history`: Retrieve the stored message history for a conversation thread (by thread\_id) from the agent’s state.
    * `GET /health`: A simple health check endpoint (returns `"ok"`).
    * It also includes a `compat_router` for backward-compatible routes (e.g., older frontend might use `/chat/stream_log` – included via `service/compat_ui.py`).
  * `service/handlers.py`: Implements the core logic for streaming and non-streaming interactions:

    * `_parse_input`: Converts a `UserInput` model into the format required by the agent (initial LangChain messages and configuration).
    * `_build_initial_state`: Prepares the initial state `dict` for the agent’s graph execution (initializing all required keys for GraphState with defaults).
    * `message_generator`: An async generator that runs the agent (`CompiledStateGraph.astream_events`) and yields Server-Sent Event data. It streams out messages in three forms: **final messages** (when a node completes with an AI message), **token events** (streaming partial LLM output for the response), and **status updates** (custom events for internal status messages). This powers the `/stream` endpoint.
    * `chat_stream_log_generator`: Similar to `message_generator`, but formats output as JSON Patch operations on structured channels (response tokens, status messages, documents). This is used for the newer streaming endpoint that separates content types for the frontend.
    * Utility functions like `should_emit_response_token` or `extract_generate_response` are defined (in other modules) to help filter and format streaming events.
  * `service/utils.py`: Additional helper functions for the service layer (e.g., converting LangChain message objects to our `ChatMessage` Pydantic model, stripping out tool invocation signals from LLM output, etc.).
  * **Purpose:** The `service` package is the **interface layer** between clients (frontend or API consumers) and the agent. It translates HTTP requests into agent invocations and streams the results back. It also handles details like attaching run IDs, managing SSE event formatting, and error handling for the API.

* **`schema/`** – Pydantic models defining request and response schemas.

  * `schema/schema.py`: Contains data models for all API inputs/outputs:

    * `UserInput` and `StreamInput` models for incoming queries (message text, model name, thread id, and a flag for streaming tokens).
    * `ChatMessage` model representing a message in the conversation (with type: human/ai/tool, content, and optional tool call info).
    * `Feedback` and `FeedbackResponse` models for feedback submissions.
    * `ChatHistoryInput` and `ChatHistory` for retrieving conversation history.
    * Models related to the streaming log structure (if using the advanced streaming endpoint with channels), e.g. `ChatStreamLogRequest` with nested `ChatInput` and `ChatConfig` describing a full conversation input.
  * **Purpose:** These schema definitions enforce input validation and provide self-documentation for the FastAPI docs. They ensure the data passed to the agent and returned to the client is well-structured and serialized appropriately (e.g., converting internal message objects to JSON-friendly form).

* **Other utility modules (in root of drsearch\_lg):**

  * `index_config.py`: Defines configurations for different vector indexes (e.g., index names mapped to attributes, response prompt templates, and any special mappings). This is used by the agent to determine how to handle different document sets.
  * `prompts_and_chains.py`: Defines reusable prompt templates and chains for various steps (like question decomposition prompts, routing prompts, answer generation prompt templates, and graders for relevance/hallucination). It pulls in the templates from `System_Prompts` and ties them with LangChain’s `PromptTemplate` and `LLMChain` utilities.
  * `System_Prompts.py`: Contains base prompt text for system instructions and templates. For example, it defines a generic response template structure (with placeholders for context and instructions), an overview template, and the actual strings for special prompts like `QUESTION_DECOMPOSER2`. These templates are combined with content at runtime to guide the LLM’s behavior.
  * `pgvector_store.py`: A wrapper around LangChain’s PGVector integration. It provides a `PgVectorStore` class with a `max_marginal_relevance_search` method and handles filtering by document IDs. This is used to retrieve documents from the Postgres/PGVector vector store, optionally excluding already used (non-relevant) documents.
  * `weaviate_filter_util.py`: Contains a utility to create a Weaviate-style filter (as a Python dict) given a list of IDs to exclude. This is used to build a filter for vector search queries (PGVector’s API can accept a filter to exclude certain document IDs).
  * `write_docs_to_file.py`: Debug utility that can append retrieved documents or marked “irrelevant” documents to a local text file. This helps with offline analysis of what the agent is retrieving or discarding. (Not used in production code paths unless debugging is enabled.)

* **`tests/`** – Test suite for the backend.

  * `tests/test_...py`: The tests cover core functionality such as the agent’s decision logic, API endpoint responses, authentication middleware, and end-to-end chat flows. For example, there are tests ensuring that the streaming endpoint returns properly formatted SSE events and that the agent can handle a multi-turn conversation.
  * The test suite uses `pytest` and `pytest-asyncio` for async tests. Mock objects and fake LLMs (via `MockEmbeddings` and `FakeListChatModel`) are used to simulate AI responses so tests are deterministic.

### Frontend Structure

* **`app/page.tsx`** – The main landing page component for the Next.js app (the chat interface).
* **`app/components/`** – Reusable UI components, including the chat message list, input box, status panel, etc.
* **`app/api/`** – Next.js API routes (if any, e.g., proxy or status endpoints; could also handle NextAuth if used for auth).
* **`app/utils/`** – Utility functions and hooks (for example, hooks to connect to the SSE stream).
* **`lib/`** – Shared libraries and context providers for the frontend (e.g., authentication utilities, stream handling logic).
* **Pages & Routing:** Next.js 13 uses the App Router; most frontend logic is in the `app/` directory structure rather than the older `pages/`. The chat UI likely lives entirely in `app/page.tsx` and child components.

The frontend is primarily concerned with rendering the chat interface, sending user queries to the backend, and handling the streamed responses. It maintains local state for the chat history and uses a **Stream Channels** architecture where backend messages are categorized into channels (response tokens, status updates, source document list) for display in different UI sections (chat window vs. side panel).

## Agent Workflow (RAG Chatbot)

*This section provides a high-level view of how the backend agent processes a query:*

1. **Initial Query & Routing:** When a user asks a question, the backend’s agent first decides how to handle it. A **“select\_index”** step (routing logic) determines if the query should use the vector database or not. For example, it distinguishes between questions that need document lookup (e.g. engineering documents vs. employee policies) and those that should be answered directly (general questions or unsupported topics).

   * If the query is related to known document domains, the agent chooses an appropriate **vector index** (e.g., “JACSKE\_Program” for design/program documents or “SEPS” for another category) and sets up a retriever for that index.
   * If the question falls outside these domains (or if configured to do a general web search), the agent may route to a **chatbot-only** path (no document retrieval, just answer based on the model’s knowledge) or a placeholder for web search (currently, web search node just flags using the chatbot).

2. **Question Decomposition:** For complex questions, the agent employs a **decompose\_question** node that uses an LLM prompt to split the user’s query into sub-questions. This helps in performing multiple focused searches. The first sub-question is usually the original question itself, followed by narrower questions targeting different aspects of the query.

3. **Document Retrieval:** Each component question is sent to the **retriever**, which performs a similarity search in the PGVector index. The agent uses a **max marginal relevance** search to get a diverse set of relevant documents. All retrieved documents from all sub-questions are collected, then passed through a **remove\_duplicate\_docs** step to eliminate overlaps.

4. **Relevance Filtering:** The retrieved documents are then scored by a **grade\_documents** node. This uses a small LLM prompt (a "retrieval grader") to decide for each document if it’s relevant (`"yes"` or `"no"`). Irrelevant documents are dropped (and optionally noted for debugging), and the relevant ones move forward. If no documents were found relevant, the agent can decide to refine the query (see next step).

5. **Optional Query Refinement:** If no useful documents are retrieved on the first pass, the agent can attempt a **transform\_query** step. This uses a “question rewriter” LLM chain to rephrase the question, after which it tries the retrieval step again (`retrieve_again` loops back into another retrieve with the new query). This loop can happen multiple times until some relevant context is found or a limit is reached.

6. **Answer Generation:** Once relevant documents are available (or if the route was chatbot-only from the start), the agent proceeds to the **generate** node. Here, it composes a prompt with a system message that includes context from the retrieved documents and instructions (e.g., “answer based on the provided context and cite sources”). It then invokes an LLM (by default, a slightly smaller or specific model if configured, e.g., `gpt-4o-mini` for faster generation) to produce the answer. The result is stored in the state (`generation` text and an `AIMessage` in `messages`).

7. **Answer Grading & Looping:** The agent may include a step to evaluate the quality of the answer (a **grade\_generation** decision). Using a structured prompt, it checks if the answer is sufficiently supported by the context (to detect hallucinations or missing info).

   * If the answer is judged **“not useful”** or not well-grounded, the workflow can branch to `retrieve_again` to fetch more documents and then regenerate an improved answer. This creates a feedback loop where the agent tries additional context if the first answer wasn’t adequate.
   * If the answer is **“useful”**, the workflow ends successfully. The final answer is considered complete and is returned to the user.

8. **Streaming Output:** As the agent executes the above steps, the backend streams events to the client:

   * **Status messages** (e.g., “🔍 Selecting optimal document index...”, “🧩 Breaking down your question...”) are sent to a status channel so the UI can display what the agent is doing.
   * **Intermediate tokens** from the LLM answer generation are sent in real-time to the response channel, so the answer appears incrementally to the user.
   * **Source documents** (once identified) can be sent in a documents channel (for example, to show citations or allow the user to view the references).
     The frontend synchronizes these via the JSON patch events, updating the UI without needing to parse raw text.

In summary, the **RAG agent** tries to answer user queries by retrieving supporting data from an internal knowledge base and ensuring the final answer is grounded in that data. It handles multi-turn chats by maintaining a `thread_id` that keeps state between questions (conversation memory stored in the agent’s `messages`). The integration of **LangGraph** allows the complex workflow above to be defined declaratively and executed step by step, while **LangChain** provides the LLM and vector store integrations.

## Pull Request Guidelines

When contributing to this project, please follow these guidelines:

* **Write Detailed Descriptions:** Clearly explain the purpose of the PR. Include context about the problem being solved and highlight major changes. If the PR addresses a specific issue, reference it (e.g., “Closes #123”).
* **Update Documentation:** For any new features or changes, update relevant documentation or comments (including this AGENT.md or module-specific AGENT.md files if the architecture changes).
* **Ensure Tests Pass:** Run the full test suite (`pytest` and frontend tests) and ensure all tests are green. If you add new functionality, include appropriate tests.
* **Follow Code Style:** Adhere to the established coding standards. Run formatters (Black, isort, Prettier) before requesting a review. Lint both Python and TypeScript code.
* **Atomic Commits:** Organize commits logically (group related changes together). This helps in reviewing and future debugging via git history.
* **No Secrets in Repo:** Do not include real API keys, secrets, or credentials in commits. Use `.env` for configuration and never commit that file. If new env variables are needed, edit `.example.env` to list them.

## Debugging Instructions

### Backend Debugging

* **Logging:** Check the backend console or log files (in the `logs/` directory if configured) for error messages or warnings. The backend logs each request and any internal errors. If `LOG_FORMAT=text` is set in .env, logs will be more human-readable during development.
* **FastAPI Docs:** Run the server locally and visit the interactive docs at `http://localhost:8011/docs`. This can be useful to manually test endpoints and examine the request/response models.
* **Insertion of Breakpoints:** Use Python’s built-in debugger (e.g., `import pdb; pdb.set_trace()`) or VSCode/PyCharm breakpoints to step through the code. Key places to set breakpoints are in `service/handlers.py` (to inspect streaming events) or in any agent node function (to inspect state changes).
* **LangGraph Visuals:** If needed, the LangGraph workflow can be visualized or printed. Since `graphviz` is a dependency, you might output the state graph structure for review (the StateGraph object can produce a DOT graph).
* **Reproduce with Tests:** If an issue is observed, try writing a small pytest that reproduces it. Many complex interactions (auth, streaming, etc.) already have tests that can be run in isolation to debug problems.

### Frontend Debugging

* **Browser DevTools:** Use Chrome/Firefox DevTools for inspecting the web app. The **Console** will show any runtime errors or network request failures (e.g., CORS issues or 401 auth failures).
* **Network Panel:** Verify that requests to the backend are correct. For streaming, you should see an EventStream connection; if it closes unexpectedly, check the backend logs for errors.
* **React Developer Tools:** Use the React DevTools extension to inspect component state and props. This is useful to ensure the stream hook (`useStreamChannels`) is updating channels as expected.
* **Mocking Backend:** If working purely on frontend styling or functionality, you can run the frontend with MSW (Mock Service Worker) intercepting API calls (the test setup includes MSW handlers). This lets you simulate backend responses without a live server.
* **Authentication Issues:** If using auth, ensure your JWT or API key is correctly configured in the frontend. The `auth.ts` in `drsearch_frontend/lib` manages attaching the Authorization header. During dev, you can disable auth (`AUTH_ENABLED=false`) to simplify testing the flow without dealing with tokens.

## Common Tasks

### Adding a New API Endpoint (Backend)

1. Create a new route function in `drsearch_lg/service/service.py` or a sub-router. Use FastAPI decorators (`@router.get/post`) with the desired path.
2. Define request/response models in `drsearch_lg/schema/schema.py` if the endpoint takes input or returns data beyond a simple message. This ensures the endpoint is documented and validated.
3. Implement the business logic. Reuse existing modules when possible (e.g., if it involves invoking the agent, use `agents` module; if it needs database access, follow patterns in other handlers).
4. Add the new route to the FastAPI app. If using a new APIRouter, include it in `service.py` via `app.include_router(new_router)`.
5. Write unit tests for the new endpoint under `drsearch_lg/tests/`. Test both success cases and potential error cases (e.g., missing fields resulting in 422, unauthorized access if applicable).
6. Update documentation (this guide or READMEs) to mention the new endpoint and its purpose.

### Adding a New Agent or Tool (Backend)

1. Define the agent’s logic similar to `rag_chatbot`. This might involve creating a new module under `drsearch_lg/agents/` (e.g., `my_agent.py`) and possibly a sub-package if it has multiple components.
2. Use LangGraph’s `StateGraph` to assemble the workflow for the agent. Define any custom nodes or prompts needed in a structure similar to `rag_chatbot_components`.
3. Register the agent in `agents/agents.py` by creating and compiling the graph, and adding it to the `agents` dict with a key name. This key will serve as the `agent_id` for API calls.
4. Extend the API if necessary: by default, the existing `/invoke` and `/stream` endpoints can handle multiple agents via the `{agent_id}` path parameter. Ensure your new agent can be invoked through those (the `agents` dict handles the selection).
5. Test the new agent thoroughly. Write tests that invoke it via the API endpoints and ensure it behaves as expected. Use fake model mode for deterministic testing.
6. Document the agent’s purpose and any special requirements in an appropriate AGENT.md (for example, create `agents/my_agent_components/AGENT.md` if complex, or update the main agents documentation).

### Adding a New Frontend Component

1. Create a new React component in `drsearch_frontend/app/components/` (or another appropriate subfolder). For example, if adding a **DocumentViewer** for source documents, create `components/DocumentViewer.tsx`.
2. Implement the component with proper props. Use TypeScript interfaces to define the prop types. For instance:

   ```tsx
   interface DocumentViewerProps { documents: SourceDocument[]; }
   ```
3. Ensure to import and use Chakra UI components for consistent styling (e.g., use Chakra’s `Box`, `Text`, etc., rather than raw HTML, when possible).
4. Add the component into the relevant page or parent component. Continuing the example, integrate `<DocumentViewer documents={documents} />` into the chat UI where source documents should display.
5. Write a simple unit test for the component if it contains logic. Use React Testing Library to render it with sample props and assert on output.
6. Manually test in the browser to fine-tune the design and fix any runtime errors or styling issues. Verify responsiveness if applicable (mobile vs desktop views).

## Important Notes

* **Environment Variables:** This project relies on environment variables for configuration. Always update the `.env` (or corresponding environment in deployment) rather than hard-coding values. The file `.example.env` in the repo lists all required or commonly used variables with descriptions.

  * Notable variables: `PGVECTOR_URL` (Postgres connection string with vector extension), `OPENAI_API_KEY` / `AZURE_OPENAI_API_KEY` (for LLM access), `AZURE_OPENAI_DEPLOYMENT_NAME` and related settings (if using Azure), `AUTH_SECRET` (if using simple bearer token auth), `AUTH_ENABLED` and Azure `TENANT_ID`/`CLIENT_ID` (for Azure AD auth).
* **LangChain/LangGraph:** The backend leverages LangChain for LLM and embeddings, and LangGraph to structure the agent’s logic. When upgrading these libraries, be mindful of breaking changes (especially LangChain’s evolving API in versions 0.x). The `LangChainBetaWarning` is filtered out by the service to keep logs clean.
* **Vector Index Management:** Ensure that the vector index (in Postgres) is populated with documents before expecting relevant answers. There might be separate scripts or ETL processes (outside this repository’s scope) to load data into the PGVector indexes. The agent’s index routing expects certain index names (see `index_config.py`). If you add new indexes or rename them, update `INDEX_CONFIG` and any logic in `select_index` or elsewhere that references them.
* **Authentication:** By default, authentication is **optional**. In development mode (`AUTH_ENABLED=False`), the AuthMiddleware simply injects a dummy user and all endpoints are accessible. In production, you can either:

  * Set `AUTH_ENABLED=True` along with Azure AD credentials to enforce JWT auth on protected endpoints.
  * Or set an `AUTH_SECRET` and leave `AUTH_ENABLED=False` to require a simple bearer token on each request (a fallback for environments without Azure AD).
  * Unprotected paths (like `/health` and those configured in `WHITELIST`) allow health checks or public access as needed.
* **Streaming vs Non-Streaming Endpoints:** The frontend primarily uses the streaming endpoint (`/stream`) to get real-time answers. The non-streaming `/invoke` is still useful for programmatic calls or simpler clients. Both go through similar logic, but `/stream` gives a more interactive experience. Keep both code paths functional. Changes in the agent or output format might require adjusting how streaming events are parsed or emitted.
* **Logging and Monitoring:** The application can log detailed events (including each step’s outputs and decisions) if enabled. For production use, it may be configured to log in JSON for aggregation. Important security note: logs might include portions of user queries or model outputs – avoid logging sensitive data or scrub it if necessary.
* **Frontend Nuances:** The React app uses Next.js App Router and React 18 features. It also includes a **StatusPanel** to show internal agent status messages. If making backend changes to status message formatting, ensure they still render well in the UI (e.g., the backend adds emojis like "🧩", and the frontend expects those).
* **Continuous Improvement:** This AGENT.md and related documentation should remain up-to-date. When significant architecture or workflow changes occur, update the relevant sections so that both developers and AI coding agents (like OpenAI Codex) can easily understand the project. The goal is to make the project as self-describing as possible for future maintainers and AI integrations.
