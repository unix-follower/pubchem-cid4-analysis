#!/usr/bin/env bash

set -ex

export PGHOST=$(minikube ip)
export PGUSER=postgres
export PGPORT=5432
export PGDATABASE=cid4_analysis
export PGPASSWORD=postgres
export DB_USER=chemist
export DB_USER_PASSWORD=$DB_USER

function delete_db() {
    dropdb --echo $PGDATABASE
}

function create_new_db() {
    # Run as Superuser
    createdb --echo --encoding='utf-8'
}

function create_vector_extension() {
    # Run as Superuser
    psql <<EOF
    CREATE EXTENSION IF NOT EXISTS vector;
    ALTER DATABASE $PGDATABASE SET session_preload_libraries = 'vector';
EOF
}

function create_age_extension() {
    # Run as Superuser
    psql <<EOF
    CREATE EXTENSION IF NOT EXISTS age;
    ALTER DATABASE $PGDATABASE SET session_preload_libraries = 'age';
EOF
}

function delete_db_user() {
    # Run as Superuser
    psql -c "DROP ROLE $DB_USER;"
}

function create_db_user() {
    # Run as Superuser
    psql <<EOF
    CREATE USER $DB_USER WITH
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    CONNECTION LIMIT 256
    PASSWORD '$DB_USER';

    -- Non-superusers need CREATE rights to database for AGE graphs
    GRANT CONNECT, CREATE ON DATABASE $PGDATABASE TO $DB_USER;

    GRANT USAGE ON SCHEMA ag_catalog TO $DB_USER;
    GRANT ALL ON SCHEMA ag_catalog TO $DB_USER;
EOF
}

function create_cid4_graph() {
    # Run as App User
    # No LOAD 'age'; needed
    PGPASSWORD=$DB_USER_PASSWORD psql -U $DB_USER <<EOF
    SET search_path = ag_catalog, public;
    SHOW search_path;
    
    SELECT ag_catalog.create_graph('cid4_graph');
EOF
}

function create_cid4_schema() {
    # Run as App User
    PGPASSWORD=$DB_USER_PASSWORD psql -U $DB_USER <<EOF
    CREATE SCHEMA IF NOT EXISTS cid4;

    GRANT ALL PRIVILEGES ON SCHEMA cid4 TO $DB_USER;
    ALTER SCHEMA cid4 OWNER TO $DB_USER;

    SET search_path = cid4, public;
    CREATE TABLE IF NOT EXISTS documents (
        doc_id TEXT PRIMARY KEY,
        doc_type TEXT NOT NULL,
        source_file TEXT NOT NULL,
        source_row_id TEXT NOT NULL,
        cid BIGINT,
        sid BIGINT,
        aid BIGINT,
        pmid TEXT,
        doi TEXT,
        taxonomy_id BIGINT,
        pathway_accession TEXT,
        title TEXT NOT NULL,
        text_payload TEXT NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        embedding vector(96) NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_cid4_documents_doc_type ON documents (doc_type);
    CREATE INDEX IF NOT EXISTS idx_cid4_documents_taxonomy_id ON documents (taxonomy_id);
EOF
}

function count_documents() {
    # Run as App User
    PGPASSWORD=$DB_USER_PASSWORD psql -U $DB_USER <<EOF
    SELECT COUNT(*) FROM cid4.documents;
EOF
}

function select_n_documents() {
    # Run as App User
    PGPASSWORD=$DB_USER_PASSWORD psql -U $DB_USER <<EOF
    SELECT * FROM cid4.documents LIMIT $1;
EOF
}


# delete_db
# create_new_db
# create_vector_extension
# create_age_extension
# delete_db_user
# create_db_user
# create_cid4_graph
# create_cid4_schema
# count_documents
# select_n_documents 10
