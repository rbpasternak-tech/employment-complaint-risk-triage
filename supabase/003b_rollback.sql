-- 003b_rollback.sql — reverses 003b_filings_rename (PENDING; only after it is applied).
BEGIN;
DROP SCHEMA legal_ingest CASCADE;   -- compat views only; verify it contains no tables first
ALTER VIEW filings.document_catalog RENAME COLUMN company_or_case TO company_case;
ALTER VIEW filings.document_catalog RENAME COLUMN data_origin TO real_synthetic;
ALTER VIEW filings.document_catalog RENAME COLUMN quality_flags TO quality_warnings;
ALTER TABLE filings.document_versions RENAME COLUMN document_kind TO kind;
ALTER TABLE filings.document_versions RENAME COLUMN data_origin TO material;
ALTER TABLE filings.document_label_audit RENAME TO document_label_history;
ALTER TABLE filings.ingest_runs RENAME TO runs;
ALTER SCHEMA filings RENAME TO legal_ingest;
-- restore original trigger function bodies
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
COMMIT;
