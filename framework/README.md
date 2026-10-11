# Decisions API vs Jev framework

One runner, one config. Both tools get the same text, questions and label choices.

```
cd /workspace/litigation-classifier/framework
python3 run.py --dry-run --limit 2    # no API calls, checks wiring
python3 run.py --limit 1              # one real doc per tool (about $0.001)
python3 run.py                        # the full dataset in config.json
python3 run.py my_config.json
```

Keys come from `OPENAI_API_KEY` and `JEV_API_KEY` (the same variables label.py uses). The runner never prints them.

**Output:** `out/<dataset>-<date>.jsonl`, one row per document per tool, with the same columns as `litigation.predictions`:
`motion_id, run_id, p_survive, predicted_outcome, features, cost_usd, latency_ms`.
`features` holds tool, claim_type, input_tokens, tokens_estimated, error, and any extra answers.
It also writes `out/<dataset>-<date>.sql`, which inserts the two `litigation.model_runs` rows and the predictions with `ON CONFLICT DO NOTHING`. Read it before running it in Supabase. Rows with errors are skipped.

**Labels** follow the post-003a vocabulary: outcome is `granted | denied | granted_in_part | not_reached`, and "partial" is mapped to granted_in_part. Claim types come from `label.py`'s `CT`. Choices marked `"@label.OUT"` are read from label.py without running it.

**Caution:** the default dataset feeds in the *ruling* text, so `stage` is `outcome_label`. That makes p_survive a labeling confidence, not a true prediction. For real prediction, point a loader at motion or complaint text only and set `"stage": "prediction"`.

## Adding a dataset (e.g. legal_ingest docs)
1. Export the documents as JSONL, one `{"id":..., "text":...}` per line. For example, from Supabase:
   `select id, body as text from legal_ingest.documents`, saved as `data/legal_ingest.jsonl`.
2. Copy `config.json` and set `"dataset": "legal_ingest_27"`, `"loader": "jsonl"`, and
   `"loader_args": {"path": "data/legal_ingest.jsonl", "id_field": "id", "text_field": "text"}`.
3. Change `schema` to fit the task. Each question is `choice` (with a `choices` dict) or `predicate`, which yields a probability. Keep a question named `outcome` / `claim_type` / `p_survive` if you want those columns filled. Other answers go into `features.extra_answers`.
4. If the docs aren't litigation motions, don't load the SQL into `litigation.predictions`, because motion_id has a foreign key to motions. Keep the JSONL, or make a matching table.
5. For a custom source, add a function to `loaders.py` that yields `{doc_id, motion_id, text}` and register it in `LOADERS`.

Adding a third tool: write a `build_*` / `parse_*` pair in run.py, add it to `ADAPTERS`, and add an entry to `config.tools`.

## Risk triage (complaint text only)
Two new configs, both reading `../prediction/cases/filings.json`, a JSON list of `{filing_id, matter_id, filing_kind, path}` with paths relative to `prediction/cases/`:
- `python3 run.py config.feature_extraction.json [--dry-run] [--limit N]` extracts class_vehicle, claim_type, factual_specificity, plaintiff_count_bucket and damages_pled, and writes `INSERT INTO triage.features`.
- `python3 run.py config.risk_score.json [--dry-run] [--limit N]` produces p_survive and risk_tier, and writes `INSERT INTO triage.risk_scores`.

**No leakage.** The `complaints` loader only accepts filing_kind complaint, amended_complaint or demand_letter. It raises an error if the text looks like a court order or opinion ("IT IS ORDERED", "MEMORANDUM OPINION", and so on). Rulings never reach a tool.
plaintiff_firm is free text, so it's filled in from the signature block by a regex or human pass, not by the classifier. The baseline (GPT/Claude) is planned as tool `baseline` in model_runs; there's no adapter for it yet.
Requires migration 007. Load the generated `.sql` through Claude with dry-run-then-apply, the same as 005.
