# Employment Complaint Risk Triage

A proof of concept for cheaply triaging risk on incoming employment complaints (and later demand letters). Cheap classifiers score each complaint high / medium / low risk **without seeing the ruling**, and the scores are checked against what judges actually decided on Rule 12(b)(6) motions to dismiss in employment class/collective actions.

> Work in progress: `claude-pack/` (dashboard handoff for Claude) and `prediction/` (complaint + motion filings for the risk test) are still being built. More files are coming.

## Data sources
- **CourtListener** (Free Law Project): batch 1, 14 rulings, plus RECAP filings.
- **GovInfo** (U.S. Courts opinions): batch 2, 14 rulings after cleanup (14 non-fits dropped, see `data/dropped.json`).
- Opinion PDFs and raw text are not in the repo. Re-fetch them with `scripts/`.

## Hosting
Supabase project `yhaahsrevxueogdwxxtl`:
- `litigation`: ground truth (cases, motions, rulings, outcomes)
- `triage`: incoming matters, filings, extracted features, risk scores, scorecards
- `legal_ingest`: separate raw SEC/DOJ intake, owned by another agent (Dots). Not touched here.

## Classification
- **OpenAI Decisions API** (`OPENAI_API_KEY`)
- **Jev** (`JEV_API_KEY`)
- Planned: a reasoning model as a third comparison.

## Current results (28 rulings)
- Both tools agree on outcome for nearly every ruling. On 13 docket-confirmed outcomes, each got 10 right, and both missed the same 3.
- Cost: about $0.64 per 1k docs (Decisions) vs. $0.31 (Jev).
- Caveat: these are outcome *labels* read from rulings, not predictions. The risk-prediction test (complaint in, ruling hidden) is in progress.

See `data/REPORT_batch1.md`, `data/REPORT_batch2.md` and `dashboard/index.html`.

## Migration run order (`supabase/`)
1. 001, 002, 003a: already applied
2. 004_one_row_per_lawsuit: done
3. 005_load_employment_12b6_batch2
4. 006_dashboard_views
5. 007_triage_schema (rollback: `007_rollback.sql`)

Dry-run each one in BEGIN … ROLLBACK before applying. **Hold 003b** (legal_ingest rename) until Dots' code is migrated.

## Setup
```bash
cp .env.example .env   # add your own keys
set -a; source .env; set +a
python framework/run.py --config framework/config.risk_score.json
```
Use your own API keys. No keys are included in this repo.

## Layout
framework/ runner + configs · dashboard/ static dashboard · supabase/ SQL + plans · risk-triage/ design + Claude instructions · data/ labels & reports · scripts/ harvest/label/analyze · claude-pack/ · prediction/

## Caveats
- Small sample (28 rulings, 13 confirmed outcomes).
- Some scripts still have box paths (`/workspace/...`) hard-coded and read the CourtListener token from `~/.secrets/`. Adjust them before running.
- Migrations 005–007 haven't been tested against a live database yet.
