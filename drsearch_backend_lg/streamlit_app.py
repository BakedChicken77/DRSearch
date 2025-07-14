import streamlit as st
import requests
import os

backend = os.getenv("BACKEND_URL", "http://localhost:8001")

st.title("DRSearch LangGraph")
query = st.text_input("Ask something")
if 'history' not in st.session_state:
    st.session_state.history = []

if st.button("Send") and query:
    resp = requests.post(f"{backend}/chat/query", json={"query": query, "user_id": "demo"})
    if resp.status_code == 200:
        data = resp.json()
        st.session_state.history.append((query, data["response"]))
    else:
        st.error("Error")

for q, a in st.session_state.history:
    st.markdown(f"**You:** {q}")
    st.markdown(f"**Bot:** {a}")
