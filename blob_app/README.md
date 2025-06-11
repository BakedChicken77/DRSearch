# blob_app

`blob_app` is a Streamlit application for exploring and managing files stored in Azure Blob Storage. It mirrors the layout and logging conventions of `pg_vector_app` and is intended for local operational workflows.

## Features

- List all containers and their blobs
- Display blob metadata such as size and last modified time
- Preview text based blobs (`.json`, `.log`, `.txt`, `.csv`)
- Download blobs locally
- Upload new files
- Delete or rename blobs
- Filter blobs by name
- View application logs or user feedback stored in blob storage

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set the `AZURE_BLOB_CONNECTION_STRING` environment variable.
3. Run the app:
   ```bash
   streamlit run app.py
   ```
