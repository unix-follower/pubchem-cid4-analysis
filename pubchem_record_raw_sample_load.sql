-- Run with `psql -f pubchem_record_raw_sample_load.sql ...` after `schema.sql`.

\set aid_payload `cat data/BIOASSAY_AID_743069.json`
INSERT INTO pubchem_record_raw (
    record_type,
    record_key,
    pubchem_record_number,
    record_accession,
    record_title,
    payload
)
VALUES (
    'AID',
    'AID:743069',
    743069,
    NULL,
    'qHTS assay to identify small molecule antagonists of the estrogen receptor alpha (ER-alpha) signaling pathway',
    :'aid_payload'::jsonb
)
ON CONFLICT (record_type, record_key) DO UPDATE
SET pubchem_record_number = EXCLUDED.pubchem_record_number,
    record_accession = EXCLUDED.record_accession,
    record_title = EXCLUDED.record_title,
    payload = EXCLUDED.payload;

\set cid_payload `cat data/COMPOUND_CID_4.json`
INSERT INTO pubchem_record_raw (
    record_type,
    record_key,
    pubchem_record_number,
    record_accession,
    record_title,
    payload
)
VALUES (
    'CID',
    'CID:4',
    4,
    NULL,
    '1-Amino-2-propanol',
    :'cid_payload'::jsonb
)
ON CONFLICT (record_type, record_key) DO UPDATE
SET pubchem_record_number = EXCLUDED.pubchem_record_number,
    record_accession = EXCLUDED.record_accession,
    record_title = EXCLUDED.record_title,
    payload = EXCLUDED.payload;

\set pathway_payload `cat data/PATHWAY_PathwayID_1186280.json`
INSERT INTO pubchem_record_raw (
    record_type,
    record_key,
    pubchem_record_number,
    record_accession,
    record_title,
    payload
)
VALUES (
    'PATHWAY',
    'PATHWAY:SMP0002032',
    NULL,
    'SMP0002032',
    'Glutathione Metabolism III',
    :'pathway_payload'::jsonb
)
ON CONFLICT (record_type, record_key) DO UPDATE
SET pubchem_record_number = EXCLUDED.pubchem_record_number,
    record_accession = EXCLUDED.record_accession,
    record_title = EXCLUDED.record_title,
    payload = EXCLUDED.payload;
