import os
from functools import lru_cache

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st
from sklearn.decomposition import PCA
import plotly.express as px

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None


@lru_cache(maxsize=1)
def get_connection():
    conn_str = os.getenv("PGVECTOR_URL")
    if not conn_str:
        st.error("PGVECTOR_URL not set")
        st.stop()
    return psycopg2.connect(conn_str, cursor_factory=psycopg2.extras.RealDictCursor)


@lru_cache(maxsize=1)
def get_embedder():
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and OpenAI:
        client = OpenAI(api_key=api_key)

        def embed(text: str) -> np.ndarray:
            resp = client.embeddings.create(model="text-embedding-ada-002", input=text)
            return np.array(resp.data[0].embedding, dtype=float)

        return embed
    elif SentenceTransformer:
        model = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
        return lambda t: model.encode(t)
    else:
        st.error("No embedding backend available")
        st.stop()


def load_collections(conn) -> pd.DataFrame:
    return pd.read_sql("SELECT id, name, cmetadata FROM langchain_pg_collection ORDER BY name", conn)


def load_embeddings(conn, collection_id: str) -> pd.DataFrame:
    sql = (
        "SELECT id, document, cmetadata, embedding "
        "FROM langchain_pg_embedding WHERE collection_id = %s ORDER BY id LIMIT 500"
    )
    return pd.read_sql(sql, conn, params=(collection_id,))


def search_embeddings(conn, collection_id: str, vector: np.ndarray, top_k: int) -> pd.DataFrame:
    sql = (
        "SELECT id, document, cmetadata, 1 - (embedding <=> %s) AS score "
        "FROM langchain_pg_embedding WHERE collection_id = %s "
        "ORDER BY embedding <-> %s LIMIT %s"
    )
    return pd.read_sql(sql, conn, params=(list(vector), collection_id, list(vector), top_k))


st.title("pgvector Explorer")
conn = get_connection()
embed = get_embedder()

collections = load_collections(conn)
collection_names = collections.set_index("name")
sel_name = st.sidebar.selectbox("Collection", collection_names.index.tolist())
collection_id = collection_names.loc[sel_name, "id"]

tab1, tab2, tab3 = st.tabs(["Browse", "Search", "Visualize"])

with tab1:
    df = load_embeddings(conn, collection_id)
    st.dataframe(df.drop(columns=["embedding"]))
    if st.button("Export to CSV"):
        st.download_button(
            "Download",
            df.to_csv(index=False).encode("utf-8"),
            f"{sel_name}.csv",
            "text/csv",
            key="download-csv",
        )
    del_id = st.text_input("Delete record ID")
    if st.button("Delete") and del_id:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM langchain_pg_embedding WHERE id = %s", (del_id,))
            conn.commit()
        st.success("Deleted record")

with tab2:
    query = st.text_input("Query")
    top_k = st.number_input("Top K", 1, 20, 5)
    if st.button("Search") and query:
        vec = embed(query)
        result = search_embeddings(conn, collection_id, vec, int(top_k))
        st.write(result.drop(columns=["embedding"], errors="ignore"))

with tab3:
    df = load_embeddings(conn, collection_id)
    if not df.empty:
        emb = np.stack(df["embedding"].tolist())
        if emb.shape[1] > 2:
            emb = PCA(n_components=2).fit_transform(emb)
        fig = px.scatter(x=emb[:, 0], y=emb[:, 1], hover_data=[df["document"]])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No embeddings found")
