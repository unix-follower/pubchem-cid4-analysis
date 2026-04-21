#!/usr/bin/env bash

set -ex

export PGHOST=localhost
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

delete_db
create_new_db
create_age_extension
delete_db_user
create_db_user
create_cid4_graph
