## app.py

import asyncio
import logging
import os
from functools import lru_cache
from typing import List

import nest_asyncio
import pandas as pd
import streamlit as st


from drsearch_backend.app.azure_search_blob_manager.AzureBlobStorageWrapperAsync import (
    AzureBlobStorageAsync,
)

import truststore
truststore.inject_into_ssl()

# Patch the event loop to allow nested usage
nest_asyncio.apply()

# Safe wrapper to run async functions in both sync and async contexts
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return asyncio.ensure_future(coro)  # You may need to `await` this if inside an `async` function
    else:
        return asyncio.run(coro)



logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> AzureBlobStorageAsync:
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        st.error("AZURE_STORAGE_CONNECTION_STRING not set")
        st.stop()
    return AzureBlobStorageAsync(conn_str)


# def run_async(coro):
#     return asyncio.run(coro)


def list_containers(client: AzureBlobStorageAsync) -> List[str]:
    return run_async(client.list_all_containers())


def list_blobs(client: AzureBlobStorageAsync, container: str):
    future = run_async(client.list_blobs_in_container(container))
    return future.result() if hasattr(future, "result") else future


def download_text(client: AzureBlobStorageAsync, container: str, blob: str) -> str:
    return run_async(client.download_blob_text(container, blob))


def upload_bytes(client: AzureBlobStorageAsync, container: str, blob: str, data: bytes):
    return run_async(client.upload_blob_bytes(container, blob, data))


def delete_blob(client: AzureBlobStorageAsync, container: str, blob: str):
    return run_async(client.delete_blob(container, blob))


def delete_container_sync(client: AzureBlobStorageAsync, container: str):
    # Create a fresh loop, run the coroutine, then close it
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(client.delete_container(container))
    finally:
        loop.close()

st.title("Azure Blob Explorer")
client = get_client()
containers = list_containers(client)
if not containers:
    st.warning("No containers found")
    st.stop()

sel_container = st.sidebar.selectbox("Container", containers)

# Create new container
with st.sidebar.expander("➕ Create New Container"):
    new_container = st.text_input("New container name")
    if st.button("Create Container") and new_container:
        run_async(client.create_container(new_container))
        st.success(f"Container '{new_container}' created.")
        st.rerun()

# Delete selected container with confirmation
with st.sidebar.expander("❌ Delete Selected Container"):
    if st.button("Delete This Container"):
        confirm = st.radio(
            f"Are you sure you want to delete '{sel_container}'?",
            options=["No", "Yes"],
            horizontal=True,
            key="confirm_delete",
        )
        if confirm == "Yes":
            future = run_async(client.delete_container(sel_container))
            if hasattr(future, "result"):
                future.result()  # wait for the deletion to finish
            st.success(f"Container '{sel_container}' deleted.")
            st.rerun()




filter_text = st.sidebar.text_input("Filter by name")

blobs = asyncio.run(client.list_blobs_in_container(sel_container))
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
        st.rerun()

st.subheader("Upload")
upload = st.file_uploader("Choose file")
if st.button("Upload") and upload is not None:
    upload_bytes(client, sel_container, upload.name, upload.getvalue())
    st.success("Uploaded")
    st.rerun()

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
