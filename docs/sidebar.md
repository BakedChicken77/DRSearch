# Sidebar Settings Overview

This document explains the Settings drawer added to the DRSearch application. The drawer allows end users to control how many reference documents are fetched for each query. It interacts with both the React frontend and the FastAPI backend.

## Frontend Implementation

### `SettingsDrawer` Component

* **Location:** `drsearch_frontend/app/components/SettingsDrawer.tsx`
* **Purpose:** Provides a minimizable sidebar allowing the user to select the number of documents retrieved per chat request.
* **UI Elements:**
  - A settings icon button positioned in the top-left corner of the chat window.
  - A Chakra `Drawer` containing a single numeric input.
* **Behavior:**
  - The drawer toggles open/closed using Chakra's `useDisclosure` hook.
  - The numeric input accepts values from **1** to **5**. The default value is **3**.
  - When the user changes the value, it calls the `setNumDocs` callback provided by the parent, updating React state.

```tsx
export function SettingsDrawer({ numDocs, setNumDocs }: { numDocs: number; setNumDocs: (v: number) => void }) {
  const { isOpen, onOpen, onClose } = useDisclosure();
  return (
    <>
      <IconButton aria-label="Open settings" icon={<SettingsIcon />} position="absolute" top={2} left={2} onClick={onOpen} />
      <Drawer placement="left" onClose={onClose} isOpen={isOpen} size="xs">
        <DrawerOverlay />
        <DrawerContent>
          <DrawerCloseButton />
          <DrawerHeader>Settings</DrawerHeader>
          <DrawerBody>
            <FormControl>
              <FormLabel>Documents to retrieve</FormLabel>
              <NumberInput min={1} max={5} value={numDocs} onChange={(_s, v) => setNumDocs(v)}>
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
            </FormControl>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </>
  );
}
```

### Integration in `ChatWindow`

* **State:** `ChatWindow` maintains a `numDocs` state variable (`useState(3)`).
* **Rendering:** The `SettingsDrawer` is rendered near the top of the chat interface:

```tsx
<SettingsDrawer numDocs={numDocs} setNumDocs={setNumDocs} />
```

* **Request Payload:** When sending a chat request, `ChatWindow` includes `num_docs_retrieved` in the JSON body:

```tsx
await fetchEventSource(`${apiBaseUrl}/chat`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    input: {
      question: messageValue,
      chat_history: chatHistory,
      index_name: selectedIndexName,
      num_docs_retrieved: numDocs,
    },
    config: { metadata: { conversation_id: conversationId } },
    include_names: ["FindDocs"],
  }),
  ...
});
```

### Summary of Frontend Flow

1. User clicks the settings icon to open the drawer.
2. User selects a value between 1 and 5.
3. The selected value is stored in `numDocs` state.
4. Each chat request includes `num_docs_retrieved: numDocs`.

## Backend Implementation

### Configuration Variable

* **File:** `drsearch_backend/app/core/chain_config.py`
* **Variable:** `_NUMBER_OF_DOCS_RETRIEVED`
* **Default:** `3`
* This global is referenced by the retriever factory to determine how many documents to fetch when constructing retrieval chains.

### Extended `ChatRequest` Model

* **File:** `drsearch_backend/app/models/chat.py`
* Adds a new field:

```python
num_docs_retrieved: int = Field(
    default=_NUMBER_OF_DOCS_RETRIEVED,
    ge=1,
    le=5,
    description="How many documents to retrieve for each query",
)
```

* The field is validated by Pydantic to ensure it stays within the allowed range.

### Engine Cache and Retrieval Count

* **File:** `drsearch_backend/app/chain/api.py`
* Chat engines are cached per `(index_name, num_docs)` pair. When a new engine is created, the global `_NUMBER_OF_DOCS_RETRIEVED` is updated so the retriever sees the correct value.

```python
def _engine_for(index_name: str, num_docs: int) -> ChatEngine:
    key = (index_name, num_docs)
    if key not in _engine_cache:
        from app.core import chain_config
        chain_config._NUMBER_OF_DOCS_RETRIEVED = num_docs
        _engine_cache[key] = ChatEngine(index_name)
    return _engine_cache[key]
```

* The `answer_chain` lambda reads `num_docs_retrieved` from the incoming request and passes it through to `_engine_for`:

```python
answer_chain: Runnable = RunnableLambda(
    lambda inputs: get_answer_chain(
        inputs.get("index_name", _DEFAULT_INDEX),
        inputs.get("num_docs_retrieved", _NUMBER_OF_DOCS_RETRIEVED),
    )
)
```

### Retriever Behavior

* **File:** `drsearch_backend/app/chain/retriever.py`
* When building a retriever, the factory references `chain_config._NUMBER_OF_DOCS_RETRIEVED` for the `k` parameter:

```python
return store.as_retriever(
    search_kwargs={"k": chain_config._NUMBER_OF_DOCS_RETRIEVED, "where_filter": filter_rag_only}
)
```

Because `_engine_for` updates the global before constructing the engine, each cached engine's retriever uses the correct document count.

### Request Handling

1. The frontend sends `num_docs_retrieved` in the request body.
2. `ChatRequest` parses and validates the value.
3. `answer_chain` uses `num_docs_retrieved` to select (or create) a chat engine configured for that count.
4. The retriever then fetches the specified number of documents when answering the query.

## Extending the Sidebar

To add new settings to the sidebar:

1. **Add State in `ChatWindow`:** Create a new `useState` hook for the setting and pass the state and setter to `SettingsDrawer`.
2. **Extend `SettingsDrawer`:** Add additional form controls (e.g., switches, selects) and call the provided setters when values change.
3. **Update `ChatRequest` and Backend Logic`:** Add corresponding fields in `app/models/chat.py` and adjust any chain or engine logic to consume the values.
4. **Include the New Fields in Requests:** When sending the fetch request in `ChatWindow`, include the new values in the `input` object.
5. **Cache Keys:** If the new setting affects engine configuration, update `_engine_for` to include it in the cache key.

With this structure, frontend changes propagate cleanly to the backend, ensuring user-selected settings control how the RAG pipeline behaves.
