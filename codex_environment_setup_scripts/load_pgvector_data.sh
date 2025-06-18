#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FILE="$SCRIPT_DIR/fake_pgvector_docs.jsonl"
# PGVECTOR_URL=${PGVECTOR_URL:-"postgresql://username:password@localhost:5432/pgvector_db"}
COLLECTION=${PGVECTOR_COLLECTION:-"JACSKE_Program"}

# export DATA_FILE PGVECTOR_URL COLLECTION
export DATA_FILE COLLECTION

poetry run python <<'PY'
import os, json, uuid, hashlib, random, psycopg2

pgurl = os.environ['PGVECTOR_URL']
collection_name = os.environ['COLLECTION']
file_path = os.environ['DATA_FILE']

conn = psycopg2.connect(pgurl)
cur = conn.cursor()
cur.execute("SELECT uuid FROM langchain_pg_collection WHERE name=%s", (collection_name,))
row = cur.fetchone()
if row:
    coll_id = row[0]
else:
    coll_id = uuid.uuid4()
    cur.execute("INSERT INTO langchain_pg_collection (name, cmetadata, uuid) VALUES (%s, %s, %s)", (collection_name, '{}', coll_id))

with open(file_path, 'r', encoding='utf-8') as f:
    docs = [json.loads(line) for line in f if line.strip()]

def embed(text: str) -> str:
    rnd = random.Random(int(hashlib.md5(text.encode()).hexdigest(), 16))
    return '[' + ','.join(f"{rnd.random():.6f}" for _ in range(1536)) + ']'

for doc in docs:
    emb = embed(doc['document'])
    cur.execute(
        "INSERT INTO langchain_pg_embedding (collection_id, embedding, document, cmetadata, custom_id, uuid) VALUES (%s, %s, %s, %s::jsonb, %s, %s)",
        (coll_id, emb, doc['document'], json.dumps(doc['metadata']), str(uuid.uuid4()), uuid.uuid4())
    )

conn.commit()
cur.close()
conn.close()
PY
