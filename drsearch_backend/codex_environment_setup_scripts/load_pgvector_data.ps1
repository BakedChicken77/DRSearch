<#  convert_bash_to_ps.ps1
    PowerShell port of fake-pgvector document loader
    ------------------------------------------------
    • Exits on first unhandled error
    • Builds DATA_FILE path relative to this script
    • Falls back to TEST_INDEX when $env:PGVECTOR_COLLECTION is not set
    • Runs the same inline Python via “poetry run python -”
#>

$ErrorActionPreference = 'Stop'        # equivalent to `set -e`

# ---------- Path setup ----------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$DataFile  = Join-Path $ScriptDir 'fake_pgvector_docs.jsonl'
# ---------------------------------

# ---------- Environment ----------
$env:DATA_FILE  = $DataFile
$env:COLLECTION = if ($env:PGVECTOR_COLLECTION) { $env:PGVECTOR_COLLECTION } else { 'TEST_INDEX' }
# ---------------------------------

# ---------- Inline Python ----------
$python = @'
import os, json, uuid, hashlib, random, psycopg2

import psycopg2.extras
psycopg2.extras.register_uuid()

pgurl           = os.environ['PGVECTOR_URL']
collection_name = os.environ['COLLECTION']
file_path       = os.environ['DATA_FILE']

conn = psycopg2.connect(pgurl)
cur  = conn.cursor()

# fetch or create collection
cur.execute("SELECT uuid FROM langchain_pg_collection WHERE name=%s", (collection_name,))
row = cur.fetchone()
if row:
    coll_id = row[0]
else:
    coll_id = uuid.uuid4()
    cur.execute(
        "INSERT INTO langchain_pg_collection (name, cmetadata, uuid) VALUES (%s, %s, %s)",
        (collection_name, '{}', coll_id)
    )

# load docs
with open(file_path, 'r', encoding='utf-8') as f:
    docs = [json.loads(line) for line in f if line.strip()]

def embed(text: str) -> str:
    rnd = random.Random(int(hashlib.md5(text.encode()).hexdigest(), 16))
    return '[' + ','.join(f"{rnd.random():.6f}" for _ in range(1536)) + ']'

for doc in docs:
    emb = embed(doc['document'])
    cur.execute(
        """
        INSERT INTO langchain_pg_embedding
            (collection_id, embedding, document, cmetadata, custom_id, uuid)
        VALUES
            (%s, %s, %s, %s::jsonb, %s, %s)
        """,
        (coll_id, emb, doc['document'], json.dumps(doc['metadata']),
         str(uuid.uuid4()), uuid.uuid4())
    )

conn.commit()
cur.close()
conn.close()
'@

# pipe the Python to stdin of “poetry run python -”
$python | poetry run python -
