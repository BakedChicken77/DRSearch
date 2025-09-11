# Acronym Handling Pipeline

This document describes how DRSearch builds and uses the list of acronym
expansions for each search index.

## 1. Data Source in PGVector

Each text chunk stored in the `langchain_pg_embedding` table may include two
arrays inside its `cmetadata` JSON column:

- `acronym_keys`: the upper‑case acronyms found in the chunk
- `acronym_values`: the corresponding definitions

The two lists are aligned by index. For example, a chunk might contain::

```json
{
  "acronym_keys": ["VDC", "AFD"],
  "acronym_values": [
    "Voltage Direct Current",
    "Arc Fault Detector"
  ]
}
```

## 2. Backend Collection and Filtering

The backend builds an acronym lookup table for each index during startup.  The
function `_fetch_acronyms()` queries PGVector for all embeddings belonging to an
index and reads the `acronym_keys`/`acronym_values` arrays from `cmetadata`
(`drsearch_backend/app/index_options.py`):

```python
SELECT e.cmetadata
FROM langchain_pg_embedding e
JOIN langchain_pg_collection c ON e.collection_id = c.uuid
WHERE c.name = %s
```

Each pair is processed with the following rules:

1. **Empty keys or values are discarded.**
2. **Keys listed in `acronyms_keys_to_ignore.json` are skipped** (comparison is
   case‑insensitive).
3. Remaining pairs are added to a dictionary where later entries override
   earlier ones, removing duplicates.

The resulting dictionary is attached to the index option returned by
`/_build_index_options`.

## 3. `/index-options` API

The `/index-options` endpoint returns the list of available indexes along with
their acronym maps.  Each `IndexOption` includes an optional `acronyms` field of
shape `{ "ADACS": "Advanced Data Acquisition and Control Syst", ... }`.
Clients may cache this data to avoid additional round‑trips during a session.

## 4. Frontend Consumption

When the frontend loads, `fetchIndexOptions` retrieves the index list.  The
`ChatWindow` component keeps the acronym map associated with the selected index
in local state.  User input is expanded on the client by `expandLastAcronym()`:

1. The function examines the last word the user typed.
2. If that word matches a key in the map (case‑insensitive), it is replaced with
   its definition and highlighted briefly for the user.

As a result, typing `"AFD "` into the chat box automatically expands to
`"Arc Fault Detector "` when the selected index contains that acronym.

## 5. Configuration

The ignore list (`drsearch_backend/app/acronyms_keys_to_ignore.json`) provides a
simple way to suppress overly generic acronyms such as `"IT"` or `"IP"`.  The
file can be edited without code changes and is loaded at runtime whenever the
backend starts.

## Summary

1. Acronym keys and values originate in PGVector chunk metadata.
2. The backend consolidates, deduplicates, and filters these pairs into a per‑index
   dictionary exposed through `/index-options`.
3. The frontend selects the map for the active index and expands typed acronyms
   immediately in the chat input.
