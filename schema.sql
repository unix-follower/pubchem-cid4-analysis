CREATE TABLE bioactivity (
    bioactivity_id BIGINT PRIMARY KEY,
    aid_type TEXT,
    activity TEXT,
    protein_accession TEXT,
    activity_type TEXT,
    activity_qualifier TEXT,
    bioassay_data_source TEXT,
    bioassay_name TEXT,
    compound_name TEXT,
    target_name TEXT,
    target_link TEXT,
    ecs TEXT,
    representative_protein_accession TEXT,
    cell_id BIGINT,
    anatomy TEXT,
    dois TEXT,
    pmcids TEXT,
    pclids TEXT,
    citations TEXT,
    bioassay_aid BIGINT,
    substance_sid BIGINT,
    compound_cid BIGINT,
    refsid BIGINT,
    gene_id BIGINT,
    pmid BIGINT,
    last_modified_date INTEGER,
    has_dose_response_curve BOOLEAN,
    rnai_bioassay BOOLEAN,
    activity_value NUMERIC,
    taxonomy_id BIGINT,
    target_taxonomy_id BIGINT,
    anatomy_id BIGINT
);

CREATE INDEX idx_bioactivity_bioassay_aid ON bioactivity (bioassay_aid);
CREATE INDEX idx_bioactivity_substance_sid ON bioactivity (substance_sid);

CREATE INDEX idx_bioactivity_gene_id
    ON bioactivity (gene_id)
    WHERE gene_id IS NOT NULL;

CREATE INDEX idx_bioactivity_pmid
    ON bioactivity (pmid)
    WHERE pmid IS NOT NULL;

CREATE INDEX idx_bioactivity_protein_accession
    ON bioactivity (protein_accession)
    WHERE protein_accession IS NOT NULL;

CREATE INDEX idx_bioactivity_taxonomy_id
    ON bioactivity (taxonomy_id)
    WHERE taxonomy_id IS NOT NULL;

CREATE TABLE consolidated_compound_taxonomy (
    id TEXT,
    data_source TEXT NOT NULL,
    compound TEXT,
    source_chemical_id TEXT NOT NULL,
    source_chemical TEXT,
    source_chemical_url TEXT,
    source_kind TEXT,
    source_id TEXT NOT NULL,
    source TEXT,
    source_url TEXT,
    source_part TEXT,
    source_organism_id BIGINT,
    source_organism TEXT,
    source_organism_url TEXT,
    taxonomy TEXT,
    evidence TEXT,
    evidence_urls TEXT,
    evidence_pmids TEXT,
    evidence_dois TEXT,
    pmcids TEXT,
    pclids TEXT,
    "references" TEXT,
    compound_cid BIGINT NOT NULL,
    taxonomy_id BIGINT NOT NULL,
    PRIMARY KEY (
        compound_cid,
        data_source,
        source_chemical_id,
        source_id,
        taxonomy_id
    )
);

CREATE INDEX idx_consolidated_compound_taxonomy_taxonomy_id
    ON consolidated_compound_taxonomy (taxonomy_id);

CREATE INDEX idx_consolidated_compound_taxonomy_source_organism_id
    ON consolidated_compound_taxonomy (source_organism_id)
    WHERE source_organism_id IS NOT NULL;

CREATE INDEX idx_consolidated_compound_taxonomy_data_source
    ON consolidated_compound_taxonomy (data_source);

CREATE TABLE cpdat (
    gid TEXT,
    cid BIGINT NOT NULL,
    category TEXT NOT NULL,
    category_description TEXT,
    categorization_type TEXT NOT NULL,
    cmpdname TEXT,
    PRIMARY KEY (cid, category, categorization_type)
);

CREATE INDEX idx_cpdat_categorization_type ON cpdat (categorization_type);
CREATE INDEX idx_cpdat_category ON cpdat (category);

CREATE TABLE iupacpka (
    gid TEXT,
    cid BIGINT NOT NULL,
    sid BIGINT NOT NULL,
    pka_type TEXT NOT NULL,
    pka NUMERIC NOT NULL,
    temperature_c NUMERIC,
    pressure TEXT,
    solvent TEXT,
    remarks TEXT,
    method TEXT,
    citation TEXT,
    pka_type_description TEXT,
    PRIMARY KEY (cid, sid, pka_type, pka, temperature_c)
);

CREATE INDEX idx_iupacpka_sid ON iupacpka (sid);
CREATE INDEX idx_iupacpka_pka_type ON iupacpka (pka_type);

CREATE TABLE literature (
    pubchem_literature_id_pclid BIGINT PRIMARY KEY,
    pmcid TEXT,
    doi TEXT,
    pmid_all TEXT,
    doi_all TEXT,
    pubchem_data_source TEXT,
    publication_type TEXT,
    title TEXT,
    abstract TEXT,
    publication_name TEXT,
    authors TEXT,
    author_affiliations TEXT,
    language TEXT,
    subject TEXT,
    url TEXT,
    image_used_as_thumbnail TEXT,
    keywords TEXT,
    citation TEXT,
    pubchem_cid TEXT,
    pubchem_sid TEXT,
    pubchem_aid TEXT,
    refchemids TEXT,
    pubchem_protein TEXT,
    pubchem_gene TEXT,
    pubchem_taxonomy TEXT,
    pubchem_target_taxonomy TEXT,
    pubchem_pathway TEXT,
    pubchem_pathway_2 TEXT,
    pubchem_cell TEXT,
    cellaccs TEXT,
    pubchem_disease TEXT,
    pubchem_reference_sid TEXT,
    pmid BIGINT,
    publication_date INTEGER
);

CREATE INDEX idx_literature_pmid
    ON literature (pmid)
    WHERE pmid IS NOT NULL;

CREATE INDEX idx_literature_pmcid
    ON literature (pmcid)
    WHERE pmcid IS NOT NULL;

CREATE INDEX idx_literature_doi
    ON literature (doi)
    WHERE doi IS NOT NULL;

CREATE TABLE patent (
    gpid BIGINT PRIMARY KEY,
    publicationnumber TEXT,
    cids TEXT,
    sids TEXT,
    title TEXT,
    abstract TEXT,
    inventors TEXT,
    assignees TEXT,
    classification TEXT,
    family TEXT,
    aids TEXT,
    geneids TEXT,
    protacxns TEXT,
    taxids TEXT,
    anatomyids TEXT,
    refsids TEXT,
    prioritydate INTEGER,
    grantdate INTEGER
);

CREATE INDEX idx_patent_publicationnumber ON patent (publicationnumber);

CREATE INDEX idx_patent_prioritydate
    ON patent (prioritydate)
    WHERE prioritydate IS NOT NULL;

CREATE TABLE pathway (
    pathwayid BIGINT PRIMARY KEY,
    pathway_accession TEXT,
    pathway_name TEXT,
    pathway_type TEXT,
    pathway_category TEXT,
    external_url TEXT,
    data_source TEXT,
    source_id TEXT,
    external_id TEXT,
    taxonomy_name TEXT,
    linked_compounds TEXT,
    linked_genes TEXT,
    linked_proteins TEXT,
    linked_literature_pmids TEXT,
    linked_ecs TEXT,
    dois TEXT,
    pmcids TEXT,
    pclids TEXT,
    citations TEXT,
    srcid BIGINT,
    taxonomy_id BIGINT,
    nonredundant BOOLEAN
);

CREATE INDEX idx_pathway_pathway_accession ON pathway (pathway_accession);
CREATE INDEX idx_pathway_data_source ON pathway (data_source);

CREATE INDEX idx_pathway_taxonomy_id
    ON pathway (taxonomy_id)
    WHERE taxonomy_id IS NOT NULL;

CREATE TABLE pathwayreaction (
    id TEXT NOT NULL,
    pubchem_pathway TEXT NOT NULL,
    source TEXT,
    source_pathway TEXT,
    source_pathway_link TEXT,
    equation TEXT,
    reaction TEXT,
    control TEXT,
    compound_cid TEXT,
    pubchem_protein TEXT,
    pubchem_gene TEXT,
    taxonomy TEXT,
    pubchem_enzyme TEXT,
    evidence_pmid TEXT,
    reactant_cid TEXT,
    product_cid TEXT,
    dois TEXT,
    pmcids TEXT,
    pclids TEXT,
    citations TEXT,
    taxonomy_id BIGINT,
    PRIMARY KEY (id, pubchem_pathway)
);

CREATE INDEX idx_pathwayreaction_source_pathway ON pathwayreaction (source_pathway);

CREATE INDEX idx_pathwayreaction_taxonomy_id
    ON pathwayreaction (taxonomy_id)
    WHERE taxonomy_id IS NOT NULL;

CREATE TABLE chemidplus (
    gid TEXT,
    compound_cid BIGINT NOT NULL,
    substance_sid BIGINT NOT NULL,
    sourceid TEXT,
    organism TEXT NOT NULL,
    test_type TEXT NOT NULL,
    route TEXT NOT NULL,
    dose TEXT NOT NULL,
    effect TEXT,
    reference TEXT,
    PRIMARY KEY (substance_sid, organism, test_type, route, dose)
);

CREATE INDEX idx_chemidplus_compound_cid ON chemidplus (compound_cid);
CREATE INDEX idx_chemidplus_test_type ON chemidplus (test_type);

CREATE TABLE springernature (
    oid BIGINT PRIMARY KEY,
    doi TEXT,
    title TEXT,
    publication_name TEXT,
    subject TEXT,
    publication_type TEXT,
    language TEXT,
    url TEXT,
    extid TEXT,
    image_used_as_thumbnail TEXT,
    cid BIGINT,
    publication_date INTEGER,
    relevance NUMERIC,
    sid BIGINT,
    pmid BIGINT,
    open_access_status BOOLEAN
);

CREATE INDEX idx_springernature_doi
    ON springernature (doi)
    WHERE doi IS NOT NULL;

CREATE INDEX idx_springernature_sid
    ON springernature (sid)
    WHERE sid IS NOT NULL;

CREATE INDEX idx_springernature_pmid
    ON springernature (pmid)
    WHERE pmid IS NOT NULL;

CREATE TABLE wiley (
    oid BIGINT PRIMARY KEY,
    pmids TEXT,
    extid TEXT,
    doi TEXT,
    title TEXT,
    publication_name TEXT,
    url TEXT,
    publication_date INTEGER,
    sid BIGINT,
    cid BIGINT
);

CREATE INDEX idx_wiley_doi
    ON wiley (doi)
    WHERE doi IS NOT NULL;

CREATE INDEX idx_wiley_sid
    ON wiley (sid)
    WHERE sid IS NOT NULL;

CREATE INDEX idx_wiley_cid
    ON wiley (cid)
    WHERE cid IS NOT NULL;

CREATE TABLE thiemechemistry (
    oid BIGINT PRIMARY KEY,
    extid TEXT,
    doi TEXT,
    title TEXT,
    publication_name TEXT,
    publication_type TEXT,
    language TEXT,
    citation TEXT,
    url TEXT,
    imageurl TEXT,
    md5 TEXT,
    publication_date INTEGER,
    pmid BIGINT,
    open_access_status BOOLEAN,
    cid BIGINT,
    sid BIGINT
);

CREATE INDEX idx_thiemechemistry_doi
    ON thiemechemistry (doi)
    WHERE doi IS NOT NULL;

CREATE INDEX idx_thiemechemistry_sid
    ON thiemechemistry (sid)
    WHERE sid IS NOT NULL;

CREATE INDEX idx_thiemechemistry_pmid
    ON thiemechemistry (pmid)
    WHERE pmid IS NOT NULL;

CREATE TABLE pubchem_record_raw (
    record_type TEXT NOT NULL,
    record_key TEXT NOT NULL,
    pubchem_record_number BIGINT,
    record_accession TEXT,
    record_title TEXT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (record_type, record_key),
    CHECK (record_type IN ('AID', 'CID', 'PATHWAY')),
    CHECK (
        (record_type IN ('AID', 'CID') AND pubchem_record_number IS NOT NULL)
        OR (record_type = 'PATHWAY' AND record_accession IS NOT NULL)
    ),
    CHECK (
        (record_type = 'PATHWAY' AND pubchem_record_number IS NULL)
        OR (record_type IN ('AID', 'CID'))
    ),
    CHECK (
        (record_type = 'PATHWAY' AND record_key = 'PATHWAY:' || record_accession)
        OR (record_type IN ('AID', 'CID') AND record_key = record_type || ':' || pubchem_record_number::TEXT)
    )
);

CREATE INDEX idx_pubchem_record_raw_record_type
    ON pubchem_record_raw (record_type);

CREATE INDEX idx_pubchem_record_raw_pubchem_record_number
    ON pubchem_record_raw (pubchem_record_number)
    WHERE pubchem_record_number IS NOT NULL;

CREATE INDEX idx_pubchem_record_raw_record_accession
    ON pubchem_record_raw (record_accession)
    WHERE record_accession IS NOT NULL;

CREATE INDEX idx_pubchem_record_raw_payload_gin
    ON pubchem_record_raw USING GIN (payload);

CREATE INDEX idx_pubchem_record_raw_aid_payload_gin
    ON pubchem_record_raw USING GIN (payload)
    WHERE record_type = 'AID';

CREATE INDEX idx_pubchem_record_raw_cid_payload_gin
    ON pubchem_record_raw USING GIN (payload)
    WHERE record_type = 'CID';

CREATE INDEX idx_pubchem_record_raw_pathway_payload_gin
    ON pubchem_record_raw USING GIN (payload)
    WHERE record_type = 'PATHWAY';

CREATE INDEX idx_pubchem_record_raw_pathway_sections_pathops
    ON pubchem_record_raw USING GIN ((payload -> 'Record' -> 'Section') jsonb_path_ops)
    WHERE record_type = 'PATHWAY';

CREATE TABLE pubchem_record_document (
    record_type TEXT NOT NULL,
    record_key TEXT NOT NULL,
    document_kind TEXT NOT NULL,
    source_file TEXT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (record_type, record_key, document_kind),
    FOREIGN KEY (record_type, record_key)
        REFERENCES pubchem_record_raw (record_type, record_key)
        ON DELETE CASCADE,
    CHECK (document_kind <> '')
);

CREATE INDEX idx_pubchem_record_document_document_kind
    ON pubchem_record_document (document_kind);

CREATE INDEX idx_pubchem_record_document_source_file
    ON pubchem_record_document (source_file)
    WHERE source_file IS NOT NULL;

CREATE INDEX idx_pubchem_record_document_payload_gin
    ON pubchem_record_document USING GIN (payload);

-- Find all records whose raw payload identifies them as Pathway records.
SELECT record_type, record_key, record_title
FROM pubchem_record_raw
WHERE payload @> '{"Record": {"RecordType": "Pathway"}}';

-- Find the compound record whose raw payload includes CID 4.
SELECT record_type, record_key, record_title
FROM pubchem_record_raw
WHERE payload @> '{"Record": {"RecordType": "CID", "RecordNumber": 4}}';

-- Find pathway records whose raw payload contains a section headed "Chemicals".
SELECT record_type, record_key, record_title
FROM pubchem_record_raw
WHERE payload @? '$.Record.Section[*] ? (@.TOCHeading == "Chemicals")';
