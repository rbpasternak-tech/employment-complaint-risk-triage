-- 003a_litigation_renames — HISTORICAL. Applied by Rebecca in Supabase on Oct 11, 2026 (migration name 003a_litigation_renames).
-- Section B of the original 003 proposal. Do not re-run. Rollback: 003a_rollback.sql.
BEGIN;
-- ===== B. litigation (just created by 001/002; cheapest time to fix) =====
ALTER TABLE litigation.label_runs RENAME TO model_runs;      -- also holds prediction runs, not just labels
COMMENT ON TABLE litigation.model_runs IS 'Provenance: one row per labeling or prediction batch (tool, model, stage, timestamp).';
ALTER TABLE litigation.rulings RENAME COLUMN outcome_decisions TO decisions_outcome;
ALTER TABLE litigation.rulings RENAME COLUMN outcome_jev TO jev_outcome;
ALTER TABLE litigation.rulings RENAME COLUMN outcome_heuristic TO heuristic_outcome;
ALTER TABLE litigation.rulings RENAME COLUMN outcome_human TO reviewer_outcome;
ALTER TABLE litigation.rulings RENAME COLUMN claim_type_decisions TO decisions_claim_type;
ALTER TABLE litigation.rulings RENAME COLUMN claim_type_jev TO jev_claim_type;

-- Label values: lowercase snake_case, short.
UPDATE litigation.rulings SET decisions_outcome='not_reached' WHERE decisions_outcome='not_decided_on_12b6';
UPDATE litigation.rulings SET jev_outcome='not_reached'       WHERE jev_outcome='not_decided_on_12b6';
UPDATE litigation.rulings SET heuristic_outcome='not_reached' WHERE heuristic_outcome='not_decided_on_12b6';
UPDATE litigation.rulings SET decisions_claim_type=lower(replace(replace(decisions_claim_type,' ','_'),'-','_')),
                              jev_claim_type=lower(replace(replace(jev_claim_type,' ','_'),'-','_'));
UPDATE litigation.cases SET claim_type=lower(replace(replace(claim_type,' ','_'),'-','_')),
                            search_bucket=lower(replace(replace(search_bucket,' ','_'),'-','_'));
-- Values in batch 1: ADA, FLSA, Title VII, other, state_wage_hour -> ada, flsa, title_vii, other, state_wage_hour. search_bucket: check SELECT DISTINCT first.
ALTER TABLE litigation.rulings ADD CONSTRAINT rulings_outcome_values CHECK (
  coalesce(decisions_outcome,'x') IN ('x','granted','denied','granted_in_part','not_reached') AND
  coalesce(jev_outcome,'x')       IN ('x','granted','denied','granted_in_part','not_reached') AND
  coalesce(outcome_final,'x')     IN ('x','granted','denied','granted_in_part','not_reached'));
COMMENT ON COLUMN litigation.rulings.outcome_final IS 'Accepted ground truth: granted | denied | granted_in_part | not_reached. Use for accuracy.';

-- case_summary references renamed columns by OID, but its output column names still say outcome_*; recreate for consistent names.
DROP VIEW litigation.case_summary;
CREATE VIEW litigation.case_summary WITH (security_invoker = true) AS
SELECT c.case_id, c.case_name, c.court, r.date_filed, c.claim_type,
       r.decisions_outcome, r.jev_outcome, r.outcome_final, r.label_status,
       (r.decisions_outcome = r.jev_outcome) AS tools_agree,
       m.motion_text_free, r.opinion_url,
       max(p.p_survive) FILTER (WHERE mr.tool='decisions') AS decisions_p_survive,
       max(p.p_survive) FILTER (WHERE mr.tool='jev')       AS jev_p_survive
FROM litigation.cases c
JOIN litigation.motions m USING (case_id)
LEFT JOIN litigation.rulings r USING (motion_id)
LEFT JOIN litigation.predictions p USING (motion_id)
LEFT JOIN litigation.model_runs mr ON mr.run_id = p.run_id
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12;
COMMENT ON VIEW litigation.case_summary IS 'Start here: one row per case with labels, agreement and predictions.';
REVOKE ALL ON ALL TABLES IN SCHEMA litigation FROM PUBLIC, anon, authenticated;

COMMIT;
