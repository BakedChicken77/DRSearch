#!/bin/bash
set -e

DB_USER="username"
DB_PASS="password"
DB_HOST="localhost"
DB_NAME="pgvector_db"
DATA_FILE="$(dirname "$0")/fake_document_chunks.json"

python3 - <<'PY'
import json, os, uuid, random
import psycopg2
from pgvector.psycopg2 import register_vector

DB_USER=os.environ.get('DB_USER', 'username')
DB_PASS=os.environ.get('DB_PASS', 'password')
DB_HOST=os.environ.get('DB_HOST', 'localhost')
DB_NAME=os.environ.get('DB_NAME', 'pgvector_db')
DATA_FILE=os.environ['DATA_FILE']

conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)
register_vector(conn)
cur = conn.cursor()
collection_uuid = str(uuid.uuid4())
cur.execute(
    "INSERT INTO public.langchain_pg_collection (name, cmetadata, uuid) VALUES (%s, %s, %s)",
    ('JACSKE_Program', '{}', collection_uuid),
)
with open(DATA_FILE, 'r', encoding='utf-8') as f:
    docs = json.load(f)
for idx, item in enumerate(docs, 1):
    emb = [random.random() for _ in range(1536)]
    cur.execute(
        "INSERT INTO public.langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id, uuid) VALUES (%s, %s, %s, %s, %s, %s)",
        (collection_uuid, emb, item['document'], json.dumps(item['cmetadata']), f'doc{idx}', str(uuid.uuid4())),
    )
conn.commit()
cur.close()
conn.close()
PY

echo "Loaded fake data into collection $collection_uuid"
