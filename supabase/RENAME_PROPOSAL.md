# Supabase naming cleanup: proposal

**Status (Oct 11, 2026, 3:30 PM ET):** Section B (litigation) is **applied** as `003a_litigation_renames` (file `003a_litigation_renames.APPLIED.sql`). The local files (label.py, analyze.py, labels.json, review.csv) are updated to match; backups are `*.pre003a`. Section A (legal_ingest → filings) is **pending** as `003b_filings_rename.sql`. Rollbacks are split into `003a_rollback.sql` and `003b_rollback.sql`. `public` is unchanged. The original single `003_rename_cleanup.sql`/`003_rollback.sql` were split and removed.

_Oct 11, 2026 (ET). Proposal only, nothing changed. Files: `003_rename_cleanup.sql`, `003_rollback.sql` (both untested; no Postgres on the box)._

## 1. Inventory (current names)
**public** (Legal Doc Catalog app, `schema.sql`)
- `public.documents`: id, user_id, title, filename, category, year, body_text, word_count, fts (generated), created_at. Indexes documents_fts_idx / _category_idx / _year_idx / _user_id_idx. 4 RLS policies "Users can view/insert/update/delete own documents".
- `public.search_documents(search_query)` → id, title, category, year, word_count, headline (security definer).
- `category` values = dummy folder names (e.g. `Employment_and_Compensation`, `M_and_A_and_Equity`).

**legal_ingest** (Dots, `pipeline/sql/*.sql`)
- `runs`: id uuid, metadata jsonb (status running|completed|partial, inserted, skipped).
- `document_versions`: id, source (`sec`|`doj`|`local_fictional_fixtures`), source_id, sha256, kind (`contract_exhibit`|`court_opinion`|`court_filing`|`synthetic`|`evaluation`), material (`real_public`|`synthetic`|`evaluation`), metadata jsonb, normalized_text, run_id (generated). Constraints document_versions_run_fk/_material_kind/_provenance/_scope_title/_text_hash, runs_metadata_identity.
- `document_labels`: document_id, display_title, company_case, topic_tags, document_date(+_is_override, _semantics), filing_date(+_is_override), provenance, edited_by, updated_at.
- `document_label_history`: audit_id, document_id, operation, old_labels, new_labels, changed_at, database_actor.
- Functions `check_document_label_edit()`, `audit_document_label_edit()`; triggers document_labels_check / _audit.
- View `document_catalog`: title, document_type (display strings), company_case, topic_tags, document_date, filing_date, source (display), real_synthetic, document_id, source_link, document_date_semantics, quality_warnings, label_provenance.

**litigation** (my 001)
- label_runs, cases, motions, rulings, predictions, view case_summary. Values: outcome `granted|denied|granted_in_part|not_decided_on_12b6`; claim type `FLSA|state_wage_hour|Title VII|ADA|other`; label_status `review|auto_accepted|human_verified|excluded`.

## 2. Naming scheme
- Everything lowercase snake_case, with plural table names (`cases`, `documents`) and singular column names.
- Schemas by domain: **`public`** = catalog app (unchanged), **`filings`** = public SEC/DOJ document corpus (was legal_ingest; "ingest" is a process, not a domain), **`litigation`** = classifier.
- Column prefixes by source: `decisions_outcome`, `jev_outcome` (sort together, read like English). The `_at` suffix is for timestamps, `_date` for dates, and `is_` for booleans.
- Label values are lowercase snake_case and short: `not_reached`, `title_vii`, `flsa`. Display text belongs in views, not in stored values.
- Every table, view and key column gets a COMMENT. Each schema has a "start here" view (`filings.document_catalog`, `litigation.case_summary`).

## 3. Rename map
| Old | New | Referenced by (needs updating) |
|---|---|---|
| schema `legal_ingest` | `filings` | pipeline.py, refresh.py, REFRESH_WORKFLOW.md, all pipeline/sql/*.sql (schema, catalog, hardening, provenance-fields, text-integrity, verify, first-pilot-ingest, negative-integrity-tests), outbox/import/connector batch SQL in pipeline/data/pilot (historical; leave), trigger function bodies (recreated in 003), PLAN.md, Claude project instructions, Dots' own notes. Grants/RLS move with the schema automatically. |
| `legal_ingest.runs` | `filings.ingest_runs` | pipeline.py, refresh.py, provenance-fields.sql (FK follows automatically) |
| `document_label_history` | `document_label_audit` | catalog.sql, audit trigger function (recreated) |
| `document_versions.kind` | `document_kind` | pipeline.py/refresh.py insert column lists, catalog view (follows automatically), CHECK constraints (follow automatically) |
| `document_versions.material` | `data_origin` | same as above |
| view col `company_case` | `company_or_case` | explorer.html if it reads the view (it reads local JSON, so likely none), connector prompts |
| view col `real_synthetic` | `data_origin` | same |
| view col `quality_warnings` | `quality_flags` | same |
| `litigation.label_runs` | `model_runs` | 001/002, PLAN.md, future predict script |
| `rulings.outcome_decisions/_jev/_heuristic/_human` | `decisions_outcome / jev_outcome / heuristic_outcome / reviewer_outcome` | 002, case_summary (recreated), PLAN.md, future dashboard |
| `rulings.claim_type_decisions/_jev` | `decisions_claim_type / jev_claim_type` | same |
| value `not_decided_on_12b6` | `not_reached` | labels.json/review.csv (local), label.py prompt choices |
| values `FLSA`, `ADA`, `Title VII` | `flsa`, `ada`, `title_vii` | label.py prompt, analyze.py |
| case_summary `p_survive_decisions/_jev` | `decisions_p_survive / jev_p_survive` | future dashboard |

**Not renamed (on purpose):**
- `document_versions` keeps its name: it really is versioned by sha256.
- Stored filings values (`real_public`, `court_filing`...) stay as they are, because the provenance CHECK requires them to match the JSON keys in `metadata`. Changing them would mean rewriting all 27 metadata rows.
- The JSON keys `kind` and `material` inside `metadata` stay too.

**Vault:** no notes reference these table names (the only grep hit was incidental). Update the "Supabase Data Layer" note's schema list once applied.

## 4. Migration
`003_rename_cleanup.sql` (one transaction):
- Renames the schema, tables, columns and view columns.
- Recreates both trigger functions, because their bodies hard-code `legal_ingest.` and plpgsql stores the body as text, so it would break silently.
- Rewrites the litigation label values and adds a CHECK on outcome values.
- Recreates `case_summary`.
- Adds COMMENTs.
- Creates a **compatibility schema `legal_ingest`** with thin security_invoker views under the old names and old column names. These are simple views, so they're auto-updatable and Dots' existing INSERT batches keep working. Grants are revoked as before.

`003_rollback.sql` reverses all of it, including the trigger bodies (copied verbatim from catalog.sql).

**Unsure / check first**
- Inserting through the compat `document_versions` view: run one INSERT in a transaction and roll it back before relying on it.
- Run `SELECT DISTINCT search_bucket FROM litigation.cases` before lowercasing.
- Pause Dots and confirm its outbox is empty before running.
- SQL is untested; dry-run with `BEGIN; ... ROLLBACK;` in the connector first.
- Drop the compat schema (`DROP SCHEMA legal_ingest CASCADE`) only after pipeline.py/refresh.py and the pipeline SQL use `filings`.

## 5. Recommendation on `public`
**Leave `public.documents` and `search_documents` as they are.**
- `js/search.js` calls `from('documents')` and `rpc('search_documents')`, and the names are already clean.
- The four RLS policies, the indexes and the security-definer function all hang off them.
- `public` must stay where it is, since it's the API-exposed schema the app uses.
- Optional and safe: add COMMENTs to `public.documents`. Optional, needs approval: rename `category` values from folder style (`M_and_A_and_Equity`) to readable labels. That's a data UPDATE plus a re-seed mapping, so it's low value.

**Order** (step 1 done):
1. Apply the litigation part now. It's brand new, so the cost is near zero.
2. Rename `legal_ingest` → `filings` with compat views, then update Dots' code.
3. Drop the compat views.

Every step needs Rebecca's approval.
