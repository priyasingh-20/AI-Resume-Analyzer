import os
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="AI Chatbot",
    page_icon="🤖",
    layout="wide",
)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []


def api(method, endpoint, **kwargs):
    return requests.request(
        method,
        f"{BACKEND_URL}{endpoint}",
        timeout=120,
        **kwargs,
    )


st.title("🤖 AI Chatbot")
st.caption("LLM-powered chatbot with document Q&A, RAG and conversation memory.")

with st.sidebar:
    st.header("📚 Knowledge Base")

    uploaded = st.file_uploader(
        "Upload PDF, TXT or DOCX",
        type=["pdf", "txt", "docx"],
    )

    if st.button("Upload & Index", use_container_width=True):
        if not uploaded:
            st.warning("Choose a document first.")
        else:
            try:
                response = api(
                    "POST",
                    "/documents/upload",
                    files={
                        "file": (
                            uploaded.name,
                            uploaded.getvalue(),
                            uploaded.type or "application/octet-stream",
                        )
                    },
                )
                if response.ok:
                    data = response.json()
                    st.success(
                        f"Uploaded. Indexed {data.get('indexed_chunks', 0)} chunks."
                    )
                else:
                    st.error(response.text)
            except requests.RequestException as exc:
                st.error(f"Backend unavailable: {exc}")

    st.divider()
    st.header("⚙️ Settings")
    top_k = st.slider("Retrieved chunks", 1, 10, 4)

    if st.button("Clear Conversation", use_container_width=True):
        try:
            api("DELETE", f"/chat/{st.session_state.session_id}")
        except requests.RequestException:
            pass
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.subheader("Documents")
    try:
        response = api("GET", "/documents")
        if response.ok:
            docs = response.json().get("documents", [])
            if docs:
                for name in docs:
                    st.write(f"📄 {name}")
            else:
                st.info("No documents uploaded.")
    except requests.RequestException:
        st.warning("Start the FastAPI backend first.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for source in message["sources"]:
                    st.markdown(
                        f"**{source['filename']}** · similarity {source['score']}"
                    )
                    st.caption(source["chunk"])


prompt = st.chat_input("Ask a question about your documents...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = api(
                    "POST",
                    "/chat",
                    json={
                        "message": prompt,
                        "session_id": st.session_state.session_id,
                        "top_k": top_k,
                    },
                )

                if response.ok:
                    data = response.json()
                    answer = data["answer"]
                    sources = data.get("sources", [])
                    st.markdown(answer)

                    if sources:
                        with st.expander("Sources"):
                            for source in sources:
                                st.markdown(
                                    f"**{source['filename']}** · similarity {source['score']}"
                                )
                                st.caption(source["chunk"])

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                    })
                else:
                    st.error(response.text)

            except requests.RequestException as exc:
                st.error(
                    "Could not connect to the backend. "
                    f"Make sure FastAPI is running at {BACKEND_URL}. Error: {exc}"
                )
