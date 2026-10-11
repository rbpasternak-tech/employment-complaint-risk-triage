# Supabase plan: litigation dataset + reorganization

## Status (updated Oct 11, 2026, 3:30 PM ET)
| File | Status |
|---|---|
| `001_litigation_schema.sql` | **Applied** |
| `002_load_employment_12b6_batch1.APPLIED.sql` | **Applied** (historical, do not re-run) |
| `003a_litigation_renames.APPLIED.sql` | **Applied** as migration `003a_litigation_renames` (rollback: `003a_rollback.sql`) |
| `003b_filings_rename.sql` | Pending: legal_ingest → filings (rollback: `003b_rollback.sql`) |
| `004_one_row_per_lawsuit.sql` | Pending: merge e04→e00, e06→e03; unique docket_id |
| `public.*` | Unchanged (by design) |

Since 003a the live names are `model_runs`, `decisions_outcome`/`jev_outcome`/`heuristic_outcome`/`reviewer_outcome`, `decisions_claim_type`/`jev_claim_type`, the value `not_reached`, lowercase claim types, and the CHECK `rulings_outcome_values`. Sections below use the original names where they describe 001/002.

_Plan only, Oct 11, 2026 (ET). No database changes made. Mac read-only; no secrets read or printed._

## 1. Write path

**What exists today (from the Mac)**
- Dots' notes (pipeline/README.md, CHECKPOINT.md, REFRESH_WORKFLOW.md): "direct REST ingestion is intentionally not enabled"; service_role has no usage on `legal_ingest`. Dots writes **idempotent SQL batches** to `pipeline/data/pilot/outbox/` and a connected assistant runs them through its **already-authenticated Supabase MCP** (project `yhaahsrevxueogdwxxtl`), then `reconcile.py` checks IDs and hashes and writes a receipt. "Python alone cannot reuse that OAuth."
- Local MCP config: `~/.claude.json`, `~/.claude/settings.json` and `claude_desktop_config.json` define **no** MCP servers. `~/.codex/config.toml` has `node_repl`, `computer-use` and `openaiDeveloperDocs`, but **no Supabase**. So the Supabase connector is the **cloud connector** in claude.ai / ChatGPT (the "GPT and Claude connected to Supabase" Rebecca mentioned), not a local one.
- Keys on disk: `legal-doc-catalog/seed/.env` holds SUPABASE_URL, SUPABASE_ANON_KEY, SEED_EMAIL, SEED_PASSWORD, DOCS_DIR (names only). `config.js` holds the legacy JWT anon key (gitignored). No service-role key anywhere. Keychain: no supabase/courtlistener items found.

**Recommendation: (a)**, run the generated SQL through her Supabase connector in Claude (or the SQL editor), following Dots' outbox pattern.
- No new secret. (b) would create a service-role key, which bypasses all RLS for the whole project. That's too much power for a 14-row load.
- It matches how `legal_ingest` was loaded, so there's one write path to reason about.
- (c) Dots' tooling is built for `document_versions` and hash reconciliation. Adapting it is more work than a 2-file migration, but reuse its idea: idempotent batches plus a verify query.
- Steps: (1) Rebecca approves. (2) In Claude with Supabase connected, run `001_litigation_schema.sql`, then `002_load_employment_12b6_batch1.sql`. (3) Run `SELECT count(*) FROM litigation.cases;` (expect 14) and `SELECT * FROM litigation.case_summary;`.
- Later, at 200–500 cases, revisit (b) with a **narrow** Postgres role (insert-only on `litigation`) instead of service_role.

## 2. Schema (`supabase/001_litigation_schema.sql`)

**Own schema `litigation`**, not inside `legal_ingest`. Different domain (case outcomes vs document corpus), different lifecycle (labels change, predictions accumulate), and clean names for GPT/Claude (`litigation.cases`). Same posture as legal_ingest: private, RLS on, no anon/authenticated grants.

| table | holds |
|---|---|
| `litigation.label_runs` | provenance: tool (decisions/jev/heuristic/human), model (`gpt-6-luna`, `jev-1.13.0`), stage, timestamp |
| `litigation.cases` | one row per lawsuit: name, court, CourtListener docket id, consensus claim type, class vehicle |
| `litigation.motions` | the 12(b)(6) motion; `motion_text_free` (currently false for all 14) |
| `litigation.rulings` | ground truth: opinion URL, short dispositive excerpt (no full text), Decisions/Jev/heuristic outcomes and claim types, `outcome_human`, `outcome_final`, `label_status`, run ids |
| `litigation.predictions` | stage 2: p_survive, features jsonb, cost, latency, one row per motion per run (empty for now) |
| `litigation.case_summary` (view) | "start here": one row per case with labels, agreement and predictions |

Every table and the view have COMMENTs so connectors can describe them.

Load file `002_load_employment_12b6_batch1.sql`: 2 label_runs + 14 cases/motions/rulings, `ON CONFLICT DO NOTHING`. `outcome_final` is set only for the 1 auto-accepted case (e09). The rest stay `review` until her spot-check. Note: the SQL was generated but **not syntax-tested** (no Postgres on the box). The run timestamp is approximate, taken from label.log's mtime.

Note: because the schema isn't exposed to the API, the connectors (which use admin SQL) can query it, but the browser dashboard can't. The dashboard will need either an exposed read-only view in `public` with RLS, or an Edge Function. Decide when building it.

## 3. Reorganization review (prioritized)

| # | Suggestion | Approval? |
|---|---|---|
| 1 | **Source of truth:** raw files stay on the Mac/repo (originals, reproducible); **Supabase is the source of truth for labels, predictions and metadata**. Write that rule into the vault note and the repo README. | Safe (docs) |
| 2 | **One write path:** all writes go via connector SQL migrations in a `supabase/migrations/` folder in bexperiments (numbered, idempotent). Connectors default to read-only use; writes only on a named migration. No service-role key on the Mac or box. | Approval for the policy |
| 3 | **Schemas by domain:** `public` = app-facing only (Legal Doc Catalog `documents`); `legal_ingest` = corpus pipeline; `litigation` = classifier; future `workflow` = `intake_items`, `decisions` (vault-planned, not created; don't build until there's a use). | Approval (litigation now, workflow later) |
| 4 | **Keys:** move `config.js` from the legacy JWT anon key to the publishable key; then consider disabling legacy JWT keys in Supabase settings. `seed/.env` holds a login email+password in plaintext: rotate or delete if seeding is done. The CourtListener token was pasted in chat: rotate it when convenient. | Approval (changes keys) |
| 5 | **Dedupe the dummy corpus:** 96 .docx on disk vs 89 rows. Likely cause: the seed script only walks `Category/Year/*.docx`, and 7 .docx sit in `Good Vibrations LTH Demo` / `Public Source Pipeline` (non-category folders). It also dedupes on (category, year, filename). Run a read-only diff via the connector (`select category, year, filename from public.documents`) to confirm. `pipeline/data/pilot/originals` duplicates the 25 public docs (fine as a cache, but mark it as cache, not source). | Diff is safe; any re-seed needs approval |
| 6 | **Label the 2 synthetic fixtures in legal_ingest** (`material='synthetic'` already exists) and exclude them from the catalog view, or move them to a test schema. | Approval |
| 7 | **RLS sanity pass:** confirm `public.documents` keeps owner-only RLS, `legal_ingest`/`litigation` stay unexposed, and no table in `public` has RLS off (Supabase security advisor). | Safe (read-only) |
| 8 | **Connector map in the vault:** Claude (cloud Supabase connector, read+write), ChatGPT (cloud connector), Codex CLI (no Supabase MCP, good, keep it that way, or add a read-only one), local scripts (publishable key only, read-only via RLS). | Safe (docs) |
| 9 | **Dots' daily refresh stays off** (she turned it off). Delete stale `outbox/` batches after receipts exist, or keep them as an audit log. | Approval to delete |
