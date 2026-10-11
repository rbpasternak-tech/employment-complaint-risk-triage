-- 003b_filings_rename.sql — PENDING (not applied). legal_ingest -> filings, with compat views.
-- Prereqs: Dots refresh OFF, outbox empty. Dry run: BEGIN; <body> ROLLBACK; first. Rollback: 003b_rollback.sql.
BEGIN;
-- ===== A. legal_ingest -> filings =====
ALTER SCHEMA legal_ingest RENAME TO filings;
COMMENT ON SCHEMA filings IS 'Public legal filings corpus (SEC contract exhibits, DOJ antitrust filings/opinions) ingested by the Dots pipeline. Private; RLS on.';

ALTER TABLE filings.runs RENAME TO ingest_runs;
ALTER TABLE filings.document_label_history RENAME TO document_label_audit;
ALTER TABLE filings.document_versions RENAME COLUMN kind TO document_kind;
ALTER TABLE filings.document_versions RENAME COLUMN material TO data_origin;
-- Note: JSON keys inside metadata ('kind','material') are NOT renamed; the provenance CHECK compares them by position-independent column reference, so it keeps working.

ALTER VIEW filings.document_catalog RENAME COLUMN company_case TO company_or_case;
ALTER VIEW filings.document_catalog RENAME COLUMN real_synthetic TO data_origin;
ALTER VIEW filings.document_catalog RENAME COLUMN quality_warnings TO quality_flags;

-- Trigger functions have schema names hard-coded in their bodies (plpgsql is stored as text), so they must be recreated.
CREATE OR REPLACE FUNCTION filings.check_document_label_edit() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,filings AS $$
DECLARE source_meta jsonb;
BEGIN
 IF TG_OP='UPDATE' AND NEW.document_id<>OLD.document_id THEN
  RAISE EXCEPTION 'Labels cannot be moved to a different version' USING ERRCODE='23514';
 END IF;
 SELECT metadata INTO source_meta FROM filings.document_versions WHERE id=NEW.document_id;
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
CREATE OR REPLACE FUNCTION filings.audit_document_label_edit() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,filings AS $$
BEGIN
 INSERT INTO filings.document_label_history(document_id,operation,old_labels,new_labels)
 VALUES(coalesce(NEW.document_id,OLD.document_id),TG_OP,
        CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END,
        CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END);
 RETURN coalesce(NEW,OLD);
END $$;
-- (the audit function writes to document_label_history; point it at the renamed table)
CREATE OR REPLACE FUNCTION filings.audit_document_label_edit() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,filings AS $$
BEGIN
 INSERT INTO filings.document_label_audit(document_id,operation,old_labels,new_labels)
 VALUES(coalesce(NEW.document_id,OLD.document_id),TG_OP,
        CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END,
        CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END);
 RETURN coalesce(NEW,OLD);
END $$;
REVOKE ALL ON FUNCTION filings.check_document_label_edit(),filings.audit_document_label_edit() FROM PUBLIC,anon,authenticated,service_role;

COMMENT ON TABLE filings.document_versions IS 'One row per ingested document version (content-addressed by sha256). normalized_text = full extracted text.';
COMMENT ON COLUMN filings.document_versions.document_kind IS 'contract_exhibit | court_opinion | court_filing | synthetic | evaluation';
COMMENT ON COLUMN filings.document_versions.data_origin IS 'real_public | synthetic | evaluation';
COMMENT ON TABLE filings.ingest_runs IS 'One row per pipeline run; details in metadata jsonb.';
COMMENT ON TABLE filings.document_labels IS 'Human/assistant label overrides per document (title, company/case, tags, dates) with provenance.';
COMMENT ON TABLE filings.document_label_audit IS 'Append-only audit trail of document_labels changes (trigger-written).';
COMMENT ON VIEW filings.document_catalog IS 'Start here: one readable row per filings document.';

-- Compatibility: old names as thin views (auto-updatable, so Dots'' INSERT batches keep working). Drop after code is updated.
CREATE SCHEMA legal_ingest;
COMMENT ON SCHEMA legal_ingest IS 'DEPRECATED compatibility views -> filings.*; drop after transition.';
CREATE VIEW legal_ingest.runs WITH (security_invoker=true) AS SELECT id, metadata FROM filings.ingest_runs;
CREATE VIEW legal_ingest.document_versions WITH (security_invoker=true) AS
  SELECT id, source, source_id, sha256, document_kind AS kind, data_origin AS material, metadata, normalized_text, run_id FROM filings.document_versions;
CREATE VIEW legal_ingest.document_labels WITH (security_invoker=true) AS SELECT * FROM filings.document_labels;
CREATE VIEW legal_ingest.document_catalog WITH (security_invoker=true) AS
  SELECT title, document_type, company_or_case AS company_case, topic_tags, document_date, filing_date, source,
         data_origin AS real_synthetic, document_id, source_link, document_date_semantics, quality_flags AS quality_warnings, label_provenance
  FROM filings.document_catalog;
REVOKE ALL ON SCHEMA legal_ingest FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA legal_ingest FROM PUBLIC, anon, authenticated, service_role;
-- UNSURE: inserting through legal_ingest.document_versions omits run_id (generated) — fine; verify one test INSERT in a rolled-back txn first.

COMMIT;
-- Verify: SELECT count(*) FROM filings.document_versions; -- 27
--         SELECT count(*) FROM legal_ingest.document_catalog; -- 27 (compat)
