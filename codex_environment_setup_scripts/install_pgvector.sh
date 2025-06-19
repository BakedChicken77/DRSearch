#!/bin/bash

set -e

# Configuration based on your connection string
DB_USER="username"
DB_PASS="password"
DB_HOST="localhost"  # assumed hostname (useful in Docker or network config)
DB_NAME="pgvector_db"

# 1. Install PostgreSQL and required packages
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib git build-essential postgresql-server-dev-16

# 2. Build and install pgvector
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
cd ..

# 3. Start PostgreSQL (fallback for non-systemd environments)
sudo service postgresql start || sudo -u postgres /usr/lib/postgresql/16/bin/postgres -D /var/lib/postgresql/16/main > /tmp/postgres.log 2>&1 &

sleep 5

# 4. Create DB user, database, enable pgvector, and create tables
sudo -u postgres psql <<EOF
DO \$\$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_user WHERE usename = '${DB_USER}'
   ) THEN
      CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
   END IF;
END
\$\$;

CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
\c ${DB_NAME}

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
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};
EOF

echo "✅ PostgreSQL with pgvector is set up and ready."
echo "Connection string: postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:5432/${DB_NAME}"
