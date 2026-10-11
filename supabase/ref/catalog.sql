-- Private editable curation, exact-version keys, audit trail and read-only browse view.
BEGIN;
CREATE TABLE IF NOT EXISTS legal_ingest.document_labels (
 document_id text PRIMARY KEY REFERENCES legal_ingest.document_versions(id),
 display_title text CHECK(display_title IS NULL OR length(trim(display_title))>0),
 company_case text,
 topic_tags text[] NOT NULL DEFAULT '{}',
 document_date date,
 document_date_is_override boolean NOT NULL DEFAULT false,
 document_date_semantics text,
 filing_date date,
 filing_date_is_override boolean NOT NULL DEFAULT false,
 provenance jsonb NOT NULL CHECK(jsonb_typeof(provenance)='object' AND coalesce(length(trim(provenance->>'basis'))>0,false)),
 edited_by text NOT NULL CHECK(length(trim(edited_by))>0),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK(document_date IS NULL OR document_date_is_override),
 CHECK(filing_date IS NULL OR filing_date_is_override),
 CHECK(NOT document_date_is_override OR coalesce(length(trim(document_date_semantics))>0,false))
);
CREATE TABLE IF NOT EXISTS legal_ingest.document_label_history (
 audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 document_id text NOT NULL REFERENCES legal_ingest.document_versions(id),
 operation text NOT NULL,
 old_labels jsonb,
 new_labels jsonb,
 changed_at timestamptz NOT NULL DEFAULT now(),
 database_actor text NOT NULL DEFAULT current_user
);
ALTER TABLE legal_ingest.document_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE legal_ingest.document_label_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON legal_ingest.document_labels,legal_ingest.document_label_history FROM PUBLIC,anon,authenticated,service_role;
REVOKE ALL ON SEQUENCE legal_ingest.document_label_history_audit_id_seq FROM PUBLIC,anon,authenticated,service_role;

CREATE OR REPLACE FUNCTION legal_ingest.check_document_label_edit() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,legal_ingest AS $$
DECLARE source_meta jsonb;
BEGIN
 IF TG_OP='UPDATE' AND NEW.document_id<>OLD.document_id THEN
  RAISE EXCEPTION 'Labels cannot be moved to a different version' USING ERRCODE='23514';
 END IF;
 SELECT metadata INTO source_meta FROM legal_ingest.document_versions WHERE id=NEW.document_id;
 IF NEW.display_title IS NOT NULL AND source_meta->>'document_role'='proposed_order' AND NEW.display_title !~* '\mproposed\M' THEN
  RAISE EXCEPTION 'Preserve Proposed in a proposed-order title' USING ERRCODE='23514';
 END IF;
 IF NEW.display_title IS NOT NULL AND (source_meta->>'title' ILIKE '%form of%' OR source_meta->>'document_status' LIKE '%filed_form%') AND NEW.display_title NOT ILIKE '%form of%' THEN
  RAISE EXCEPTION 'Preserve Form of in a filed-form title' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' AND (to_jsonb(NEW)-ARRAY['updated_at','edited_by','provenance']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['updated_at','edited_by','provenance']) AND NEW.provenance IS NOT DISTINCT FROM OLD.provenance THEN
  RAISE EXCEPTION 'Update provenance when changing labels or date corrections' USING ERRCODE='23514';
 END IF;
 NEW.updated_at=now();
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION legal_ingest.audit_document_label_edit() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,legal_ingest AS $$
BEGIN
 INSERT INTO legal_ingest.document_label_history(document_id,operation,old_labels,new_labels)
 VALUES(coalesce(NEW.document_id,OLD.document_id),TG_OP,
        CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END,
        CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END);
 RETURN coalesce(NEW,OLD);
END $$;
REVOKE ALL ON FUNCTION legal_ingest.check_document_label_edit(),legal_ingest.audit_document_label_edit() FROM PUBLIC,anon,authenticated,service_role;
DROP TRIGGER IF EXISTS document_labels_check ON legal_ingest.document_labels;
CREATE TRIGGER document_labels_check BEFORE INSERT OR UPDATE ON legal_ingest.document_labels FOR EACH ROW EXECUTE FUNCTION legal_ingest.check_document_label_edit();
DROP TRIGGER IF EXISTS document_labels_audit ON legal_ingest.document_labels;
CREATE TRIGGER document_labels_audit AFTER INSERT OR UPDATE OR DELETE ON legal_ingest.document_labels FOR EACH ROW EXECUTE FUNCTION legal_ingest.audit_document_label_edit();

CREATE OR REPLACE VIEW legal_ingest.document_catalog WITH(security_invoker=true) AS
SELECT coalesce(l.display_title,d.metadata->>'title') AS title,
 CASE
  WHEN d.kind='synthetic' THEN 'Fictional fixture'
  WHEN d.kind='evaluation' THEN 'Evaluation dataset document'
  WHEN d.metadata->>'document_role'='proposed_order' THEN 'Proposed judgment (party filing)'
  WHEN d.metadata->>'document_role'='allegations' AND d.metadata->>'title' ILIKE '%amended%' THEN 'Amended complaint (allegations)'
  WHEN d.metadata->>'document_role'='allegations' THEN 'Complaint (allegations)'
  WHEN d.metadata->>'document_role'='party_argument' THEN 'Brief / motion (party argument)'
  WHEN d.metadata->>'document_role'='government_filed_explanation' THEN 'Competitive impact statement (government filing)'
  WHEN d.metadata->>'document_role'='judicial_order' THEN 'Court order / judgment'
  WHEN d.kind='court_opinion' THEN 'Court opinion'
  WHEN d.metadata->>'document_status' LIKE '%filed_form%' THEN 'Contract exhibit — form'
  WHEN d.kind='contract_exhibit' AND d.metadata->>'title' ILIKE '%amendment%' THEN 'Credit agreement amendment'
  WHEN d.kind='contract_exhibit' THEN 'Corporate contract exhibit'
  ELSE replace(d.kind,'_',' ')
 END AS document_type,
 coalesce(l.company_case,d.metadata->>'case_family',CASE WHEN d.metadata ? 'cik' THEN 'CIK '||(d.metadata->>'cik') END) AS company_case,
 coalesce(l.topic_tags,'{}'::text[]) AS topic_tags,
 CASE WHEN l.document_date_is_override THEN l.document_date
      ELSE coalesce(nullif(d.metadata->>'document_date','')::date,nullif(d.metadata->>'contract_date','')::date) END AS document_date,
 CASE WHEN l.filing_date_is_override THEN l.filing_date ELSE nullif(d.metadata->>'filing_date','')::date END AS filing_date,
 CASE d.source WHEN 'sec' THEN 'SEC EDGAR' WHEN 'doj' THEN 'DOJ public case files' WHEN 'local_fictional_fixtures' THEN 'Local fictional fixtures' ELSE d.source END AS source,
 CASE d.material WHEN 'real_public' THEN 'Real public' WHEN 'synthetic' THEN 'Synthetic' ELSE 'Evaluation' END AS real_synthetic,
 d.id AS document_id,d.metadata->>'url' AS source_link,
 CASE WHEN l.document_date_is_override THEN l.document_date_semantics
      WHEN d.metadata->>'contract_date' IS NOT NULL THEN coalesce(d.metadata->>'date_basis','Agreement dated-as-of; not confirmed effective date')
      WHEN d.metadata->>'document_date' IS NOT NULL THEN 'Source document date' END AS document_date_semantics,
 d.metadata->'quality_flags' AS quality_warnings,
 l.provenance AS label_provenance
FROM legal_ingest.document_versions d LEFT JOIN legal_ingest.document_labels l ON l.document_id=d.id;
REVOKE ALL ON legal_ingest.document_catalog FROM PUBLIC,anon,authenticated,service_role;
COMMIT;
