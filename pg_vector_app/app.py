import logging
import os
import json
from functools import lru_cache

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
import streamlit as st
from sklearn.decomposition import PCA
import plotly.express as px


# Use system trust store for SSL certificate verification.
# This ensures that Python honors certificates trusted by Windows (e.g., Microsoft RSA TLS CA 02),
# which may be missing from certifi's default bundle. Required for Azure US Gov endpoints.
import truststore  # system trust store for SSL certs
truststore.inject_into_ssl()

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Environment variables
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_EMBEDDER = os.getenv("AZURE_OPENAI_EMBEDDER")
PGVECTOR_URL = os.getenv("PGVECTOR_URL")

try:
    from openai import AzureOpenAI
except ImportError:
    AzureOpenAI = None
    logger.debug("AzureOpenAI SDK not available")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None
    logger.debug("SentenceTransformer not available")


@lru_cache(maxsize=1)
def load_config(path="config.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


config = load_config()


def delete_entire_collection(conn, collection_name: str) -> bool:
    """
    Delete a collection row (by name) and all embeddings that reference it.
    Returns True when the collection is gone, False if it never existed.
    """
    with conn.begin() as connection:
        uuid_row = connection.execute(
            text("""
                SELECT uuid
                  FROM public.langchain_pg_collection
                 WHERE name = :name
                 FOR UPDATE
            """),
            {"name": collection_name},
        ).fetchone()

        if uuid_row is None:
            logger.warning("Collection %s not found – nothing deleted.", collection_name)
            return False

        col_uuid = uuid_row[0]   # UUID of the collection

        # 1️⃣ delete embeddings first (FK-safe order)
        connection.execute(
            text("DELETE FROM public.langchain_pg_embedding WHERE collection_id = :uid"),
            {"uid": col_uuid},
        )

        # 2️⃣ delete the collection itself
        connection.execute(
            text("DELETE FROM public.langchain_pg_collection WHERE uuid = :uid"),
            {"uid": col_uuid},
        )

    # ── verification pass ──
    with conn.connect() as c:
        still_exists = c.execute(
            text("SELECT 1 FROM public.langchain_pg_collection WHERE uuid = :uid"),
            {"uid": col_uuid},
        ).fetchone()

    logger.info("Collection %s deletion status = %s", collection_name,
                "removed" if not still_exists else "still present")
    return still_exists is None


@lru_cache(maxsize=1)
def get_connection():
    logger.debug("Getting database connection")
    conn_str = PGVECTOR_URL
    if not conn_str:
        logger.error("PGVECTOR_URL environment variable is not set")
        st.error("PGVECTOR_URL not set")
        st.stop()

    engine = create_engine(conn_str)
    logger.info("SQLAlchemy engine created")

    with engine.connect() as conn:
        result = conn.execute(text("SHOW search_path"))
        logger.info("Python search_path: %s", result.fetchone()[0])
    return engine


@lru_cache(maxsize=1)
def get_embedder():
    logger.debug("Initializing embedder")
    if AZURE_OPENAI_API_KEY and AzureOpenAI:
        logger.info("Using AzureOpenAI embedder")
        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
        )

        def embed(text: str) -> np.ndarray:
            logger.debug("Calling AzureOpenAI embed for text: %s", text[:50])
            resp = client.embeddings.create(model=AZURE_OPENAI_EMBEDDER, input=text)
            vec = np.array(resp.data[0].embedding, dtype=float)
            logger.debug("Received embedding of length %d", len(vec))
            return vec

        return embed

    elif SentenceTransformer:
        logger.info("Using SentenceTransformer embedder")
        model = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))

        def embed(text: str) -> np.ndarray:
            logger.debug("Encoding text with SentenceTransformer: %s", text[:50])
            vec = model.encode(text)
            logger.debug("Received embedding of length %d", len(vec))
            return vec

        return embed

    else:
        logger.error("No embedding backend available")
        st.error("No embedding backend available")
        st.stop()


def load_collections(conn) -> pd.DataFrame:
    logger.debug("Loading collections from database")
    sql = """
      SELECT uuid, name, cmetadata
        FROM public.langchain_pg_collection
       ORDER BY name
    """
    df = pd.read_sql(sql, conn)
    logger.info("Loaded %d collections", len(df))
    return df


def load_embeddings(conn, collection_id: str) -> pd.DataFrame:
    logger.debug("Loading embeddings for collection_id: %s", collection_id)
    sql = (
        "SELECT uuid, document, cmetadata, embedding "
        "FROM public.langchain_pg_embedding WHERE collection_id = %s "
        "ORDER BY uuid LIMIT 500"
    )
    df = pd.read_sql(sql, conn, params=(collection_id,))
    logger.info("Loaded %d embeddings", len(df))
    return df


def search_embeddings(conn, collection_id: str, vector: np.ndarray, top_k: int) -> pd.DataFrame:
    logger.debug("Searching embeddings: collection_id=%s, top_k=%d", collection_id, top_k)

    # Convert numpy vector to plain Python list of floats
    vector_list = [float(x) for x in vector]

    sql = (
        "SELECT uuid, document, cmetadata, 1 - (embedding <=> %s::vector) AS score "
        "FROM public.langchain_pg_embedding WHERE collection_id = %s "
        "ORDER BY embedding <-> %s::vector LIMIT %s"
    )

    params = (vector_list, collection_id, vector_list, top_k)
    logger.debug("SQL params: %s", params)

    df = pd.read_sql(sql, conn, params=params)
    logger.info("Search returned %d results", len(df))
    return df


# Streamlit UI
st.title("pgvector Explorer")
logger.debug("Starting Streamlit app")

conn = get_connection()
embed = get_embedder()

# Load and filter collections
collections = load_collections(conn)
logger.debug("Raw UUIDs:\n%s", collections["uuid"].tolist())

collections["uuid_str"] = collections["uuid"].astype(str)
logger.debug("UUID strings:\n%s", collections["uuid_str"].tolist())

invalid = collections[~collections["uuid_str"].str.match(r"^[0-9a-fA-F\-]{36}$")]
logger.warning("Filtered out invalid UUIDs:\n%s", invalid)

collections = collections[collections["uuid_str"].str.match(r"^[0-9a-fA-F\-]{36}$")]
logger.debug("Filtered down to %d valid collections", len(collections))

options = {row["name"]: row["uuid"] for _, row in collections.iterrows()}

if not options:
    logger.warning("No valid collections found")
    st.warning("No valid collections found in the database.")
    st.stop()

# Flag used to coordinate rerun after deletion
if "delete_triggered" not in st.session_state:
    st.session_state["delete_triggered"] = False

# Dropdown selection
sel_name = st.sidebar.selectbox("Collection", list(options.keys()))

# Deletion UI
if st.sidebar.button("Delete Collection", key="delete_collection_btn"):
    st.session_state["confirming_delete"] = True

# Confirming block
if st.session_state.get("confirming_delete", False):
    st.sidebar.warning(
        f"⚠️ Are you sure you want to delete **all data** in collection **“{sel_name}”**?"
    )
    if st.sidebar.button("Yes, delete", key="confirm_delete_yes"):
        success = delete_entire_collection(conn, sel_name)
        st.session_state["confirming_delete"] = False
        if success:
            st.session_state["delete_triggered"] = True
        else:
            st.sidebar.error("Collection not found – nothing deleted.")
    if st.sidebar.button("Cancel", key="confirm_delete_no"):
        st.session_state["confirming_delete"] = False
        st.sidebar.info("Deletion cancelled.")

if st.session_state["delete_triggered"]:
    st.session_state["delete_triggered"] = False
    st.experimental_rerun()

if sel_name is None:
    st.warning("Please select a collection.")
    st.stop()

collection_id = options[sel_name]
logger.info("Selected collection: %s (UUID: %s)", sel_name, collection_id)
# New: Total Documents Loaded
total_docs_df = pd.read_sql(
    """
    SELECT COUNT(DISTINCT cmetadata->>'filename') AS unique_filenames
      FROM public.langchain_pg_embedding
     WHERE collection_id = %s
    """,
    conn,
    params=(collection_id,),
)
total_docs = total_docs_df["unique_filenames"].iloc[0]
st.sidebar.markdown(f"**Total Documents Loaded:** {total_docs}")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Browse", "Search", "Visualize", "Files"])

with tab1:
    logger.debug("Tab: Browse")
    df = load_embeddings(conn, collection_id)
    # extract nested cmetadata into top-level columns per config
    out = pd.DataFrame()
    for key in config["columns"]:
        if key in df.columns:
            out[key] = df[key]
        else:
            out[key] = df["cmetadata"].apply(
                lambda cm: cm.get(key) if isinstance(cm, dict) else None
            )
    # reorder columns exactly as in config
    out = out[config["columns"]]
    st.dataframe(out)

    if st.button("Export to CSV"):
        st.download_button(
            "Download",
            out.to_csv(index=False).encode("utf-8"),
            f"{sel_name}.csv",
            "text/csv",
            key="download-csv",
        )

    del_id = st.text_input("Delete record ID")
    if st.button("Delete") and del_id:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.langchain_pg_embedding WHERE uuid = %s", (del_id,))
            conn.commit()
        st.success("Deleted record")

with tab2:
    logger.debug("Tab: Search")
    query = st.text_input("Query")
    top_k = st.number_input("Top K", 1, 20, 5)
    if st.button("Search") and query:
        logger.debug("Search button pressed with query: %s", query)
        vec = embed(query)
        result = search_embeddings(conn, collection_id, vec, int(top_k))
        st.write(result.drop(columns=["embedding"], errors="ignore"))

with tab3:
    logger.debug("Tab: Visualize")
    df = load_embeddings(conn, collection_id)
    embedding_list = df["embedding"].tolist()

    # Ensure all embeddings are valid lists of floats
    valid_embeddings = [e for e in embedding_list if isinstance(e, list) and len(e) > 1]

    if len(valid_embeddings) == 0:
        logger.warning("No valid embeddings for PCA visualization")
        st.warning("No valid embeddings to visualize.")
    else:
        emb = np.stack(valid_embeddings)
        logger.debug("Embedding array shape: %s", emb.shape)

        if emb.shape[1] > 2:
            emb = PCA(n_components=2).fit_transform(emb)

        fig = px.scatter(x=emb[:, 0], y=emb[:, 1], hover_data=[df["document"][:len(emb)]])
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    files_df = pd.read_sql(
        "SELECT DISTINCT cmetadata->>'filename' AS filename "
        "FROM public.langchain_pg_embedding WHERE collection_id = %s ORDER BY filename",
        conn,
        params=(collection_id,)
    )
    st.dataframe(files_df)
