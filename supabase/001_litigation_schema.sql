-- 001_litigation_schema.sql  — Employment 12(b)(6) classifier dataset (PLAN; not yet applied)
-- Private schema, same security posture as legal_ingest: RLS on, no anon/authenticated grants.
-- Idempotent: safe to re-run.
BEGIN;
CREATE SCHEMA IF NOT EXISTS litigation;
COMMENT ON SCHEMA litigation IS 'Litigation classifier: federal employment class-action cases, 12(b)(6) motions, rulings (ground-truth labels) and model predictions. Source: CourtListener (public domain opinions).';

CREATE TABLE IF NOT EXISTS litigation.label_runs (
  run_id       text PRIMARY KEY,
  tool         text NOT NULL CHECK (tool IN ('decisions','jev','heuristic','human')),
  model        text,            -- e.g. gpt-6-luna, jev-1.13.0
  stage        text NOT NULL CHECK (stage IN ('outcome_label','prediction')),
  started_at   timestamptz NOT NULL DEFAULT now(),
  notes        text
);
COMMENT ON TABLE litigation.label_runs IS 'Provenance: one row per labeling/prediction batch (tool, model, timestamp).';

CREATE TABLE IF NOT EXISTS litigation.cases (
  case_id        text PRIMARY KEY,          -- local id e.g. e00
  case_name      text NOT NULL,
  court          text NOT NULL,             -- CourtListener court id, e.g. dcd
  docket_id      bigint,                    -- CourtListener docket id
  claim_type     text,                      -- consensus: FLSA | state_wage_hour | title_vii | ada | other
  class_vehicle  text CHECK (class_vehicle IN ('flsa_collective','rule23_class','both','unknown')),
  search_bucket  text,
  source         text NOT NULL DEFAULT 'courtlistener',
  created_at     timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE litigation.cases IS 'One row per lawsuit in the employment class-action sample.';

CREATE TABLE IF NOT EXISTS litigation.motions (
  motion_id      text PRIMARY KEY,
  case_id        text NOT NULL REFERENCES litigation.cases(case_id),
  motion_type    text NOT NULL DEFAULT '12b6',
  motion_text_url text,                     -- RECAP doc URL if available
  motion_text_free boolean NOT NULL DEFAULT false,
  complaint_url  text
);
COMMENT ON TABLE litigation.motions IS 'The motion to dismiss being predicted. Predictions must read only motion/complaint text, never the ruling.';

CREATE TABLE IF NOT EXISTS litigation.rulings (
  ruling_id      text PRIMARY KEY,
  motion_id      text NOT NULL REFERENCES litigation.motions(motion_id),
  date_filed     date,
  opinion_url    text NOT NULL,
  dispositive_excerpt text,                 -- short quote; full text is NOT stored
  outcome_decisions text,                   -- granted | denied | granted_in_part | not_decided_on_12b6
  outcome_jev       text,
  outcome_heuristic text,
  claim_type_decisions text,
  claim_type_jev       text,
  outcome_human  text,                      -- Rebecca's spot-check (review.csv your_label)
  outcome_final  text,                      -- accepted ground truth
  label_status   text NOT NULL DEFAULT 'review' CHECK (label_status IN ('review','auto_accepted','human_verified','excluded')),
  decisions_run_id text REFERENCES litigation.label_runs(run_id),
  jev_run_id       text REFERENCES litigation.label_runs(run_id),
  labeled_at     timestamptz
);
COMMENT ON TABLE litigation.rulings IS 'Court ruling on the motion = ground truth. Outcome labels from Decisions and Jev with provenance via label_runs.';
COMMENT ON COLUMN litigation.rulings.outcome_final IS 'Use this for accuracy scoring. NULL until auto-accepted or human-verified.';

CREATE TABLE IF NOT EXISTS litigation.predictions (
  prediction_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  motion_id      text NOT NULL REFERENCES litigation.motions(motion_id),
  run_id         text NOT NULL REFERENCES litigation.label_runs(run_id),
  p_survive      numeric CHECK (p_survive BETWEEN 0 AND 1),
  predicted_outcome text,
  features       jsonb,     -- class definition pleaded, facts sufficiency, arbitration/waiver, timeliness...
  cost_usd       numeric,
  latency_ms     integer,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (motion_id, run_id)
);
COMMENT ON TABLE litigation.predictions IS 'Stage-2 predictions: one row per motion per tool run. Empty until predictions are run.';

CREATE OR REPLACE VIEW litigation.case_summary WITH (security_invoker = true) AS
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

ALTER TABLE litigation.label_runs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE litigation.cases       ENABLE ROW LEVEL SECURITY;
ALTER TABLE litigation.motions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE litigation.rulings     ENABLE ROW LEVEL SECURITY;
ALTER TABLE litigation.predictions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON SCHEMA litigation FROM anon, authenticated;
COMMIT;
