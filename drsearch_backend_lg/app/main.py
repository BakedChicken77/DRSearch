from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .routers import chat, documents

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DRSearch LG")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(documents.router)

@app.get("/")
async def root():
    return {"message": "LangGraph RAG API is running!"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
