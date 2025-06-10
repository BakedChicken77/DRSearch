# pg_vector_app

This Streamlit application provides an interactive interface for exploring and managing
embeddings stored in PostgreSQL using the `pgvector` extension. It allows you to browse
records, run similarity searches, and perform basic maintenance tasks on the vector index.

## Features

- View available collections and inspect stored documents/embeddings.
- Execute semantic search over the selected collection with similarity scoring.
- Filter or delete individual records.
- Upload new text files to insert into the collection.
- Export query results to CSV.
- Visualize vector distributions with a simple 2‑D scatter plot.

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Ensure the `PGVECTOR_URL` environment variable points to your database.
3. Run the app:
   ```bash
   streamlit run app.py
   ```

An optional `OPENAI_API_KEY` can be set to embed search queries via OpenAI.
If not provided, a lightweight `sentence-transformers` model will be used instead.
