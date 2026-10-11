-- 007_rollback.sql — removes the triage schema and restores model_runs checks. litigation data untouched.
-- Fails if any model_runs rows use the new stages/tools; delete those runs first if intended.
BEGIN;
DROP SCHEMA IF EXISTS triage CASCADE;
ALTER TABLE litigation.model_runs DROP CONSTRAINT IF EXISTS model_runs_tool_check;
ALTER TABLE litigation.model_runs ADD CONSTRAINT model_runs_tool_check CHECK (tool IN ('decisions','jev','heuristic','human'));
ALTER TABLE litigation.model_runs DROP CONSTRAINT IF EXISTS model_runs_stage_check;
ALTER TABLE litigation.model_runs ADD CONSTRAINT model_runs_stage_check CHECK (stage IN ('outcome_label','prediction'));
COMMIT;
