-- Enable pgvector and create table
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS documents;
CREATE TABLE documents (
    id        BIGSERIAL PRIMARY KEY,
    filename  TEXT,
    content   TEXT,
    embedding VECTOR(1536)
);

-- Recommended IVF-Flat index for cosine similarity (docs > few thousand)
CREATE INDEX IF NOT EXISTS idx_documents_embedding
    ON documents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
