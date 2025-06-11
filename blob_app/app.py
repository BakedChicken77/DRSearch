import asyncio
import logging
import os
from functools import lru_cache
from typing import List

import pandas as pd
import streamlit as st

from drsearch_backend.app.azure_search_blob_manager.AzureBlobStorageWrapperAsync import (
    AzureBlobStorageAsync,
)
import truststore

truststore.inject_into_ssl()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> AzureBlobStorageAsync:
    conn_str = os.getenv("AZURE_BLOB_CONNECTION_STRING")
    if not conn_str:
        st.error("AZURE_BLOB_CONNECTION_STRING not set")
        st.stop()
    return AzureBlobStorageAsync(conn_str)


def run_async(coro):
    return asyncio.run(coro)


def list_containers(client: AzureBlobStorageAsync) -> List[str]:
    return run_async(client.list_all_containers())


def list_blobs(client: AzureBlobStorageAsync, container: str):
    return run_async(client.list_blobs_in_container(container))


def download_text(client: AzureBlobStorageAsync, container: str, blob: str) -> str:
    return run_async(client.download_blob_text(container, blob))


def upload_bytes(client: AzureBlobStorageAsync, container: str, blob: str, data: bytes):
    return run_async(client.upload_blob_bytes(container, blob, data))


def delete_blob(client: AzureBlobStorageAsync, container: str, blob: str):
    return run_async(client.delete_blob(container, blob))


st.title("Azure Blob Explorer")
client = get_client()
containers = list_containers(client)
if not containers:
    st.warning("No containers found")
    st.stop()

sel_container = st.sidebar.selectbox("Container", containers)
filter_text = st.sidebar.text_input("Filter by name")

blobs = list_blobs(client, sel_container)
rows = [
    {
        "name": b.name,
        "size": getattr(b, "size", None),
        "last_modified": getattr(b, "last_modified", None),
    }
    for b in blobs
]
df = pd.DataFrame(rows)
if filter_text:
    df = df[df["name"].str.contains(filter_text)]

st.subheader("Blobs")
st.dataframe(df)

sel_blob = st.selectbox("Blob", df["name"].tolist() if not df.empty else [])

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("View") and sel_blob:
        content = download_text(client, sel_container, sel_blob)
        st.code(content)

with col2:
    if st.button("Download") and sel_blob:
        content = download_text(client, sel_container, sel_blob)
        st.download_button(
            label="Download file",
            data=content.encode("utf-8"),
            file_name=sel_blob,
            mime="text/plain",
        )

with col3:
    if st.button("Delete") and sel_blob:
        delete_blob(client, sel_container, sel_blob)
        st.experimental_rerun()

st.subheader("Upload")
upload = st.file_uploader("Choose file")
if st.button("Upload") and upload is not None:
    upload_bytes(client, sel_container, upload.name, upload.getvalue())
    st.success("Uploaded")
    st.experimental_rerun()

# Logs tab
st.subheader("Logs / Feedback")
log_container = st.text_input("Container with logs", "logs")
if st.button("Load Logs"):
    log_blobs = list_blobs(client, log_container)
    names = [b.name for b in log_blobs if b.name.endswith((".log", ".txt", ".json"))]
    for name in names:
        st.write(f"### {name}")
        content = download_text(client, log_container, name)
        st.code(content, language="text")
