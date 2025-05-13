-- Connect to the database
\connect recordmanager_db

BEGIN;

-- Enable the uuid-ossp extension to generate UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop the existing doc_records table if it exists
DROP TABLE IF EXISTS doc_records;

-- Create the new doc_records table with the updated schema
CREATE TABLE doc_records (
    uuid VARCHAR PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id VARCHAR NOT NULL,
    namespace VARCHAR NOT NULL,
    hash VARCHAR,
    last_modified TIMESTAMP,
    ingestion_date TIMESTAMP,
    updated_at DOUBLE PRECISION,
    text_key VARCHAR DEFAULT '0',
    embedder_model VARCHAR DEFAULT '0',
    html_summary_model VARCHAR DEFAULT '0',
    html_summary_prompt VARCHAR DEFAULT '0',
    max_chunk_size INTEGER DEFAULT 0,
    html_summaries INTEGER DEFAULT 0,
    CONSTRAINT uix_group_id_namespace UNIQUE (group_id, namespace)
);

-- Create indexes for doc_records
CREATE INDEX ix_group_id_namespace ON doc_records (group_id, namespace);
CREATE INDEX ix_doc_records_uuid ON doc_records (uuid);

-- Drop the existing upsertion_record table if it exists
DROP TABLE IF EXISTS upsertion_record;

-- Create the new upsertion_record table with the updated schema
CREATE TABLE upsertion_record (
    uuid VARCHAR PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR,
    namespace VARCHAR NOT NULL,
    group_id VARCHAR,
    updated_at DOUBLE PRECISION,
    CONSTRAINT uix_key_namespace UNIQUE (key, namespace)
);

-- Create indexes for upsertion_record
CREATE INDEX ix_key_namespace ON upsertion_record (key, namespace);
CREATE INDEX ix_upsertion_record_uuid ON upsertion_record (uuid);
CREATE INDEX ix_upsertion_record_key ON upsertion_record (key);
CREATE INDEX ix_upsertion_record_namespace ON upsertion_record (namespace);
CREATE INDEX ix_upsertion_record_updated_at ON upsertion_record (updated_at);

COMMIT;



--psql -U username -h postgres_drsearch -p 5432 -d recordmanager_db -f Delete_doc_records_table_and_create_a_new_table.sql

