-- 006_dashboard_views.sql — NOT YET APPLIED. Read-only views for a Supabase-backed dashboard.
-- Assumes 001 + 003a applied (model_runs, decisions_outcome/jev_outcome, ...). Works before or after 004.
-- Idempotent: CREATE OR REPLACE only; no table changes, no data writes. Same posture as 001: security_invoker, no anon/authenticated grants.
BEGIN;

-- One row per ruling: both tools side by side, agreement, and correctness where ground truth exists.
CREATE OR REPLACE VIEW litigation.tool_comparison WITH (security_invoker = true) AS
SELECT c.case_id, c.case_name, c.court, c.docket_id, c.claim_type, r.ruling_id, r.motion_id, r.date_filed, r.opinion_url,
       r.decisions_outcome, r.jev_outcome, r.heuristic_outcome, r.reviewer_outcome, r.outcome_final, r.label_status,
       r.decisions_claim_type, r.jev_claim_type,
       (r.decisions_outcome IS NOT NULL AND r.decisions_outcome = r.jev_outcome)        AS outcome_agree,
       (r.decisions_claim_type IS NOT NULL AND r.decisions_claim_type = r.jev_claim_type) AS claim_type_agree,
       CASE WHEN r.outcome_final IS NULL THEN NULL ELSE r.decisions_outcome = r.outcome_final END AS decisions_correct,
       CASE WHEN r.outcome_final IS NULL THEN NULL ELSE r.jev_outcome = r.outcome_final END       AS jev_correct
FROM litigation.rulings r
JOIN litigation.motions m USING (motion_id)
JOIN litigation.cases c ON c.case_id = m.case_id;
COMMENT ON VIEW litigation.tool_comparison IS 'Dashboard: one row per ruling with Decisions vs Jev calls, agreement and correctness vs outcome_final.';

-- Headline numbers (single row).
CREATE OR REPLACE VIEW litigation.tool_summary WITH (security_invoker = true) AS
SELECT count(*)                                              AS rulings,
       count(DISTINCT case_id)                               AS cases,
       count(*) FILTER (WHERE outcome_agree)                 AS outcome_agree_n,
       round(avg(outcome_agree::int)
             FILTER (WHERE decisions_outcome IS NOT NULL AND jev_outcome IS NOT NULL), 4) AS outcome_agree_rate,
       round(avg(claim_type_agree::int) FILTER (WHERE decisions_claim_type IS NOT NULL), 4) AS claim_type_agree_rate,
       count(*) FILTER (WHERE outcome_final IS NOT NULL)     AS ground_truth_n,
       round(avg(decisions_correct::int), 4)                 AS decisions_accuracy,
       round(avg(jev_correct::int), 4)                       AS jev_accuracy
FROM litigation.tool_comparison;
COMMENT ON VIEW litigation.tool_summary IS 'Dashboard KPIs: agreement and accuracy (accuracy only over rulings with outcome_final).';

-- Outcome mix by claim type, per tool (long format, easy to chart).
CREATE OR REPLACE VIEW litigation.outcome_mix_by_claim_type WITH (security_invoker = true) AS
SELECT coalesce(claim_type,'other') AS claim_type, 'decisions'::text AS tool, decisions_outcome AS outcome, count(*) AS n
FROM litigation.tool_comparison GROUP BY 1,2,3
UNION ALL
SELECT coalesce(claim_type,'other'), 'jev', jev_outcome, count(*) FROM litigation.tool_comparison GROUP BY 1,2,3;
COMMENT ON VIEW litigation.outcome_mix_by_claim_type IS 'Dashboard chart: ruling count by claim type, tool and outcome.';

-- Rulings where the tools disagree on outcome or claim type.
CREATE OR REPLACE VIEW litigation.tool_disagreements WITH (security_invoker = true) AS
SELECT * FROM litigation.tool_comparison
WHERE NOT outcome_agree OR (decisions_claim_type IS NOT NULL AND NOT claim_type_agree);
COMMENT ON VIEW litigation.tool_disagreements IS 'Dashboard review queue: Decisions and Jev disagree.';

-- Per-run cost/latency from predictions (filled by framework/run.py loads). cost_per_1k_docs = avg cost x 1000.
CREATE OR REPLACE VIEW litigation.run_costs WITH (security_invoker = true) AS
SELECT mr.run_id, mr.tool, mr.model, mr.stage, mr.started_at,
       count(p.prediction_id)                         AS calls,
       sum(p.cost_usd)                                AS cost_usd,
       round(avg(p.cost_usd) * 1000, 4)               AS cost_per_1k_docs,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY p.latency_ms) AS median_latency_ms,
       sum((p.features->>'input_tokens')::bigint)     AS input_tokens
FROM litigation.model_runs mr
LEFT JOIN litigation.predictions p USING (run_id)
GROUP BY mr.run_id, mr.tool, mr.model, mr.stage, mr.started_at;
COMMENT ON VIEW litigation.run_costs IS 'Dashboard: cost, cost per 1,000 docs and latency per model run.';

REVOKE ALL ON litigation.tool_comparison, litigation.tool_summary, litigation.outcome_mix_by_claim_type,
              litigation.tool_disagreements, litigation.run_costs FROM PUBLIC, anon, authenticated;
COMMIT;
