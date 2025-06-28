#!/bin/bash
set -e  # exit on first error

# Configuration
DB_USER="username"
DB_PASS="password"
DB_HOST="localhost"
DB_NAME="pgvector_db"

# 1. Install utilities for codename detection and key management
sudo apt-get update
sudo apt-get install -y lsb-release gnupg curl software-properties-common

# 2. Add PostgreSQL Global Development Group (PGDG) APT repository
CODENAME=$(. /etc/os-release && echo "$UBUNTU_CODENAME")
echo "deb http://apt.postgresql.org/pub/repos/apt ${CODENAME}-pgdg main" \
  | sudo tee /etc/apt/sources.list.d/pgdg.list

# 3. Import the PGDG signing key securely
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
  | gpg --dearmor \
  | sudo tee /etc/apt/trusted.gpg.d/pgdg.gpg > /dev/null

# 4. Update and install PostgreSQL 15 and build dependencies
sudo apt-get update
sudo apt-get install -y postgresql-15 postgresql-contrib-15 postgresql-server-dev-15 \
                        git build-essential

# 5. Build and install pgvector extension
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
cd ..

# 6. Start PostgreSQL (with fallback if systemd isn’t available)
sudo service postgresql start || {
  PGDATA=$(sudo -u postgres psql -tAc "SHOW data_directory;")
  sudo -u postgres postgres -D "$PGDATA" > /tmp/postgres.log 2>&1 &
  sleep 5
}

# 7. Create user, database, enable vector extension, and schema
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
    name VARCHAR,
    cmetadata JSON,
    uuid UUID PRIMARY KEY
);

CREATE TABLE public.langchain_pg_embedding (
    collection_id UUID REFERENCES public.langchain_pg_collection(uuid) ON DELETE CASCADE,
    embedding vector(1536),
    document VARCHAR,
    cmetadata JSONB,
    custom_id VARCHAR,
    uuid UUID PRIMARY KEY
);

CREATE INDEX ix_cmetadata_gin ON public.langchain_pg_embedding USING gin (cmetadata jsonb_path_ops);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};
EOF

echo "✅ PostgreSQL 15 with pgvector is set up and ready."
echo "Connection string: postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:5432/${DB_NAME}"
