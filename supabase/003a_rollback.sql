-- 003a_rollback.sql — reverses 003a_litigation_renames (applied). Use only if needed.
BEGIN;
ALTER TABLE litigation.rulings DROP CONSTRAINT IF EXISTS rulings_outcome_values;
DROP VIEW litigation.case_summary;
UPDATE litigation.rulings SET decisions_outcome='not_decided_on_12b6' WHERE decisions_outcome='not_reached';
UPDATE litigation.rulings SET jev_outcome='not_decided_on_12b6' WHERE jev_outcome='not_reached';
UPDATE litigation.rulings SET heuristic_outcome='not_decided_on_12b6' WHERE heuristic_outcome='not_reached';
-- claim types back to original strings
UPDATE litigation.rulings SET decisions_claim_type = CASE decisions_claim_type WHEN 'flsa' THEN 'FLSA' WHEN 'ada' THEN 'ADA' WHEN 'title_vii' THEN 'Title VII' ELSE decisions_claim_type END,
                              jev_claim_type       = CASE jev_claim_type       WHEN 'flsa' THEN 'FLSA' WHEN 'ada' THEN 'ADA' WHEN 'title_vii' THEN 'Title VII' ELSE jev_claim_type END;
UPDATE litigation.cases SET claim_type    = CASE claim_type    WHEN 'flsa' THEN 'FLSA' WHEN 'ada' THEN 'ADA' WHEN 'title_vii' THEN 'Title VII' ELSE claim_type END,
                            search_bucket = CASE search_bucket WHEN 'flsa' THEN 'FLSA' WHEN 'ada' THEN 'ADA' WHEN 'title_vii' THEN 'Title VII' ELSE search_bucket END;
ALTER TABLE litigation.rulings RENAME COLUMN decisions_outcome TO outcome_decisions;
ALTER TABLE litigation.rulings RENAME COLUMN jev_outcome TO outcome_jev;
ALTER TABLE litigation.rulings RENAME COLUMN heuristic_outcome TO outcome_heuristic;
ALTER TABLE litigation.rulings RENAME COLUMN reviewer_outcome TO outcome_human;
ALTER TABLE litigation.rulings RENAME COLUMN decisions_claim_type TO claim_type_decisions;
ALTER TABLE litigation.rulings RENAME COLUMN jev_claim_type TO claim_type_jev;
ALTER TABLE litigation.model_runs RENAME TO label_runs;
CREATE VIEW litigation.case_summary WITH (security_invoker = true) AS
SELECT c.case_id, c.case_name, c.court, r.date_filed, c.claim_type,
       r.outcome_decisions, r.outcome_jev, r.outcome_final, r.label_status,
       (r.outcome_decisions = r.outcome_jev) AS tools_agree,
       m.motion_text_free, r.opinion_url,
       max(p.p_survive) FILTER (WHERE lr.tool='decisions') AS p_survive_decisions,
       max(p.p_survive) FILTER (WHERE lr.tool='jev')       AS p_survive_jev
FROM litigation.cases c
JOIN litigation.motions m USING (case_id)
LEFT JOIN litigation.rulings r USING (motion_id)
LEFT JOIN litigation.predictions p USING (motion_id)
LEFT JOIN litigation.label_runs lr ON lr.run_id = p.run_id
GROUP BY c.case_id, c.case_name, c.court, r.date_filed, c.claim_type, r.outcome_decisions,
         r.outcome_jev, r.outcome_final, r.label_status, m.motion_text_free, r.opinion_url;
COMMENT ON VIEW litigation.case_summary IS 'Start here: one row per case with labels, agreement and predictions.';

COMMIT;
