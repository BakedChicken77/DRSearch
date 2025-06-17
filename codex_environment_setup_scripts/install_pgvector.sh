#!/bin/bash

set -e

# Step 1: Install PostgreSQL and dependencies
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib git build-essential postgresql-server-dev-16

# Step 2: Build and install pgvector extension
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
cd ..

# Step 3: Start PostgreSQL manually (fallback if service doesn't exist)
sudo service postgresql start || sudo -u postgres /usr/lib/postgresql/16/bin/postgres -D /var/lib/postgresql/16/main > /tmp/postgres.log 2>&1 &

sleep 5  # give it time to start

# Step 4: Create database, enable extension, and create tables
sudo -u postgres psql <<'EOF'
CREATE DATABASE vecdb;
\c vecdb
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE public.langchain_pg_collection (
    name character varying,
    cmetadata json,
    uuid uuid PRIMARY KEY
);

CREATE TABLE public.langchain_pg_embedding (
    collection_id uuid REFERENCES public.langchain_pg_collection(uuid) ON DELETE CASCADE,
    embedding vector(1536),
    document character varying,
    cmetadata jsonb,
    custom_id character varying,
    uuid uuid PRIMARY KEY
);

CREATE INDEX ix_cmetadata_gin ON public.langchain_pg_embedding USING gin (cmetadata jsonb_path_ops);
EOF

echo "✅ PostgreSQL with pgvector is ready. Database: vecdb"
