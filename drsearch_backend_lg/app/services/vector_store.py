from typing import List, Dict, Any
from langchain_community.vectorstores.pgvector import PGVector
from langchain_openai import AzureOpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader, TextLoader
import os
from ..config import get_settings

settings = get_settings()

class VectorStoreService:
    """Service for interacting with pgvector."""

    def __init__(self) -> None:
        self.embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            deployment_name=settings.AZURE_OPENAI_DEPLOYMENT,
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15")
        )
        self.store = PGVector(
            connection_string=settings.DATABASE_URL,
            embedding_function=self.embeddings,
            collection_name="documents",
        )
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    async def add_document(self, file_path: str, metadata: Dict[str, Any]) -> int:
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        else:
            loader = TextLoader(file_path)
        docs = loader.load()
        docs = self.splitter.split_documents(docs)
        for d in docs:
            d.metadata.update(metadata)
        self.store.add_documents(docs)
        return len(docs)

    async def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        results = self.store.similarity_search_with_score(query, k=k)
        out = []
        for doc, score in results:
            out.append({"content": doc.page_content, "metadata": doc.metadata, "score": score})
        return out

    async def delete_document(self, filename: str) -> None:
        self.store.delete(filter={"filename": {"$eq": filename}})

    async def list_documents(self) -> List[Dict[str, Any]]:
        docs = self.store.similarity_search("*")  # PGVector doesn't support list; using hack
        filenames = {}
        for doc in docs:
            fname = doc.metadata.get("filename", "")
            filenames.setdefault(fname, 0)
            filenames[fname] += 1
        return [{"filename": k, "chunk_count": v} for k, v in filenames.items()]
