-- 007_triage_schema.sql — Risk-triage layer (DRAFT, not applied).
-- Run order: 004 (applied) -> 005 -> 006 -> 007. Requires litigation.cases/motions/rulings/model_runs.
-- Design: litigation stays as the OUTCOME / ground-truth store (nothing moved, no data touched).
-- New schema `triage` holds inbound matters, their filings, extracted features and risk scores.
-- Idempotent: safe to re-run. Private: RLS on, no anon/authenticated grants. Rollback: 007_rollback.sql.
BEGIN;
CREATE SCHEMA IF NOT EXISTS triage;
COMMENT ON SCHEMA triage IS 'Risk triage of inbound complaints/demand letters: matters, filings, features, risk scores. Outcomes live in litigation.';

-- One row per inbound matter (a lawsuit OR a pre-suit demand letter). case_id links to litigation when a court outcome exists.
CREATE TABLE IF NOT EXISTS triage.matters (
  matter_id     text PRIMARY KEY,                 -- e.g. e00, g12, dl-2026-001
  matter_kind   text NOT NULL CHECK (matter_kind IN ('lawsuit','demand_letter')),
  title         text NOT NULL,
  court         text,
  case_id       text UNIQUE REFERENCES litigation.cases(case_id),
  source        text NOT NULL,                    -- courtlistener | govinfo | recap | justia | upload
  received_at   date,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Documents per matter. Text stored only for prediction inputs (complaint, motion, demand letter); rulings by URL.
CREATE TABLE IF NOT EXISTS triage.filings (
  filing_id     text PRIMARY KEY,
  matter_id     text NOT NULL REFERENCES triage.matters(matter_id),
  filing_kind   text NOT NULL CHECK (filing_kind IN ('complaint','amended_complaint','motion_to_dismiss','opposition','ruling','demand_letter','other')),
  filed_on      date,
  url           text,
  text          text,
  is_model_input boolean GENERATED ALWAYS AS (filing_kind IN ('complaint','amended_complaint','demand_letter')) STORED,
  sha256        text,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS filings_matter_idx ON triage.filings(matter_id);
COMMENT ON COLUMN triage.filings.is_model_input IS 'Only these filings may be sent to Decisions/Jev/baseline. Rulings and motions never are (no outcome leakage).';

-- Features pulled by a cheap tool from ONE input filing.
CREATE TABLE IF NOT EXISTS triage.features (
  filing_id     text NOT NULL REFERENCES triage.filings(filing_id),
  run_id        text NOT NULL REFERENCES litigation.model_runs(run_id),
  class_vehicle text,          -- flsa_collective | rule23_class | both | individual | unknown
  claim_type    text,          -- flsa | state_wage_hour | title_vii | ada | adea | other
  factual_specificity text,    -- specific | mixed | boilerplate
  plaintiff_firm text,
  plaintiff_count_bucket text, -- 1 | 2_10 | 11_100 | 100_plus | unknown
  damages_pled  text,          -- none | under_1m | 1m_10m | over_10m | unspecified
  extra         jsonb NOT NULL DEFAULT '{}',
  cost_usd      numeric, latency_ms int,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (filing_id, run_id)
);

-- Risk score per filing per tool run (decisions | jev | baseline reasoning model | human).
CREATE TABLE IF NOT EXISTS triage.risk_scores (
  filing_id     text NOT NULL REFERENCES triage.filings(filing_id),
  run_id        text NOT NULL REFERENCES litigation.model_runs(run_id),
  p_survive     numeric CHECK (p_survive BETWEEN 0 AND 1),
  risk_tier     text CHECK (risk_tier IN ('high','medium','low')),
  rationale     text,
  cost_usd      numeric, latency_ms int,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (filing_id, run_id)
);

-- Allow the new stages/tools in the shared provenance table.
ALTER TABLE litigation.model_runs DROP CONSTRAINT IF EXISTS label_runs_tool_check;
ALTER TABLE litigation.model_runs DROP CONSTRAINT IF EXISTS model_runs_tool_check;
ALTER TABLE litigation.model_runs ADD CONSTRAINT model_runs_tool_check CHECK (tool IN ('decisions','jev','heuristic','human','baseline'));
ALTER TABLE litigation.model_runs DROP CONSTRAINT IF EXISTS label_runs_stage_check;
ALTER TABLE litigation.model_runs DROP CONSTRAINT IF EXISTS model_runs_stage_check;
ALTER TABLE litigation.model_runs ADD CONSTRAINT model_runs_stage_check CHECK (stage IN ('outcome_label','prediction','feature_extraction','risk_score'));

-- Backfill one matter per existing lawsuit (no copy of ruling text; just a link).
INSERT INTO triage.matters(matter_id, matter_kind, title, court, case_id, source)
SELECT c.case_id, 'lawsuit', c.case_name, c.court, c.case_id, c.source FROM litigation.cases c
ON CONFLICT (matter_id) DO NOTHING;

-- Outcome per matter: survived = any claim survived 12(b)(6). Later: class cert, MSJ, settlement columns.
CREATE OR REPLACE VIEW triage.outcomes WITH (security_invoker = true) AS
SELECT mt.matter_id, r.outcome_final,
       CASE WHEN r.outcome_final IN ('denied','granted_in_part') THEN true
            WHEN r.outcome_final = 'granted' THEN false END AS survived_12b6,
       r.date_filed AS ruled_on, r.opinion_url
FROM triage.matters mt
JOIN litigation.motions m ON m.case_id = mt.case_id AND m.motion_type = '12b6'
JOIN litigation.rulings r ON r.motion_id = m.motion_id;

-- Dashboard: each scored filing next to the real outcome.
CREATE OR REPLACE VIEW triage.risk_vs_outcome WITH (security_invoker = true) AS
SELECT f.matter_id, f.filing_id, f.filing_kind, mr.tool, mr.model, s.p_survive, s.risk_tier,
       o.outcome_final, o.survived_12b6,
       CASE WHEN o.survived_12b6 IS NULL OR s.risk_tier IS NULL THEN NULL
            ELSE (s.risk_tier = 'high') = o.survived_12b6 END AS tier_matches_outcome,
       s.cost_usd
FROM triage.risk_scores s
JOIN triage.filings f USING (filing_id)
JOIN litigation.model_runs mr USING (run_id)
LEFT JOIN (SELECT DISTINCT ON (matter_id) * FROM triage.outcomes ORDER BY matter_id, ruled_on DESC NULLS LAST) o USING (matter_id);

CREATE OR REPLACE VIEW triage.tool_scorecard WITH (security_invoker = true) AS
SELECT tool, model, count(*) AS scored,
       count(*) FILTER (WHERE survived_12b6 IS NOT NULL) AS with_outcome,
       avg(tier_matches_outcome::int) AS tier_accuracy,
       avg(CASE WHEN survived_12b6 IS NOT NULL THEN power(p_survive - survived_12b6::int, 2) END) AS brier,
       sum(cost_usd) AS cost_usd
FROM triage.risk_vs_outcome GROUP BY tool, model;

ALTER TABLE triage.matters     ENABLE ROW LEVEL SECURITY;
ALTER TABLE triage.filings     ENABLE ROW LEVEL SECURITY;
ALTER TABLE triage.features    ENABLE ROW LEVEL SECURITY;
ALTER TABLE triage.risk_scores ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA triage FROM anon, authenticated;
REVOKE ALL ON SCHEMA triage FROM anon, authenticated;
COMMIT;
