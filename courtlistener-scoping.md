# CourtListener scoping for the 12(b)(1) survival classifier
_Read-only research, Oct 10, 2026 (PT). Nothing was signed up for._

## 1. What CourtListener offers (REST API v4, base `https://www.courtlistener.com/api/rest/v4/`)
| Need | Endpoint |
|---|---|
| Full-text search (opinions, RECAP, oral args) | `search/?q=...&type=o` (opinions) / `type=r` (RECAP dockets+docs) / `type=rd` (RECAP documents only) |
| Opinion text | `opinions/{id}/` (fields `plain_text`, `html_with_citations`), grouped under `clusters/` → `dockets/` |
| Dockets | `dockets/`, `docket-entries/` |
| Filed documents (motions, complaints) | `recap-documents/` (`plain_text`, `filepath_local` PDF); `recap-fetch/` can buy missing docs from PACER with *your own* PACER login |
| Courts | `courts/` (ids like `dcd`, `nysd`, `cand`; `jurisdiction=FD` = federal district) |

**Auth / limits:** Search worked **without a token** in testing. Detail endpoints (`opinions/`) returned **401** unauthenticated, so a token is required for text. Tokens are free: make a free account at courtlistener.com, then copy the token from your profile's API page. Send it as `Authorization: Token <key>`. The default limit is 5,000 requests/hour per user. Bulk data (quarterly CSV dumps of opinions, dockets and RECAP on S3) is also free for large pulls.

**Licensing:** Case-law opinions are public domain. CourtListener's own data is offered free, including for bulk and commercial use, and Free Law Project asks for attribution and asks heavy users to use bulk files instead of hammering the API. Check the current Terms page before running anything at production scale.

## 2. Volume estimate (unauthenticated `search/`, type=o, run today)
Query: `"12(b)(1)" AND "subject matter jurisdiction"`
| Slice | Count |
|---|---|
| All courts, 2023–2025 | 1,425 |
| …per year 2023 / 2024 / 2025 | 428 / 445 / 552 |
| Federal appellate only, 2023–2025 | 262 |
| ⇒ District + other (approx.) | ~1,150 |
| Just 5 big districts (D.D.C., S.D.N.Y., N.D. Cal., S.D. Tex., N.D. Ill.) | 582 |
| With `AND (granted OR denied)` | 1,406 |
| RECAP docs/dockets mentioning "12(b)(1)" (all years) | ~107,000 |

Takeaway: about 1,100 district opinions from 2023–2025 is plenty for a sample of 200–500. Note that CourtListener's district-court opinion coverage is incomplete, so D.D.C. and the big districts are overrepresented.

## 3. Proposals
### (a) Sampling and labeling
- Draw about 400 district opinions from 2023–2025. Stratify by court and year, and cap D.D.C. at about 25%, since it dominates federal-agency standing cases.
- Weak labeling: give Decisions/Jev the full opinion and ask for one of `granted | denied | granted_in_part | moot/not_reached | not_a_12b1_ruling`, plus a quoted dispositive sentence. If both models agree and the quote supports the label, auto-accept. If they disagree, Rebecca or I review by hand. Also hand-check a random 10–15% (about 50) to measure label accuracy.
- Define "survives" = denied (or granted with leave to amend, if you choose; flag it separately). Throw out moot or not-reached rulings.
- 200 examples are enough for a first signal and 400–500 for stable accuracy numbers. Expect the classes to be unbalanced, since grants are common.

### (b) Leakage → recommendation
The opinion states the outcome, so a classifier that sees the opinion is cheating. **Recommended: classify from the motion to dismiss and the opposition, or the complaint, pulled via RECAP**, and use the opinion only for the label. Join them by docket id; the motion is usually the docket entry the order cites. This matches the real use, which is predicting before the ruling. Fallback for an early prototype: the opinion's "background" section only, cut before "Discussion/Analysis" and stripped of words like grant/deny/dismiss. That's still leaky, since judges frame facts toward the result, so report it separately. Gap: not every opinion has RECAP motion papers, so expect to keep maybe 30–60% of the sample (estimate). Buying missing docs via PACER costs $0.10/page, capped at $3 per document.

### (c) Supabase design (new tables in private `legal_ingest`)
```sql
cases(id uuid pk, cl_docket_id bigint unique, court_id text, case_name text,
      nature_of_suit text, date_filed date, run_id fk runs)
motions(id uuid pk, case_id fk cases, motion_type text default '12b1',
        cl_recap_document_id bigint, document_version_id fk document_versions, -- motion text
        opposition_version_id fk document_versions, filed_date date)
rulings(id uuid pk, motion_id fk motions, cl_opinion_id bigint,
        document_version_id fk document_versions, outcome text check (outcome in
        ('granted','denied','granted_in_part','moot','not_reached')),
        label_source text, -- 'decisions'|'jev'|'consensus'|'human'
        label_confidence real, evidence_quote text, reviewed_by text, reviewed_at timestamptz)
predictions(id uuid pk, motion_id fk motions, model text, model_version text,
        input_kind text, -- 'motion'|'complaint'|'redacted_opinion'
        p_survive real, sub_answers jsonb, run_id fk runs, created_at timestamptz)
```
Opinion and motion text go in the existing `document_versions`. Labels can also be written to `document_labels`/`document_label_history` so the catalog UI keeps working. Add a `split` column (train/test) on `motions` so the test set stays fixed.

### (d) Next steps
1. **Rebecca:** create a free CourtListener account and send me the API token via a secure card. (Optional: a PACER account, only if you want to buy missing motion papers.)
2. Me/Dots: add a CourtListener source to the pipeline, pull a stratified sample of about 400 opinions, and map their dockets to RECAP motion documents.
3. Weak-label the outcomes with Decisions and Jev, then hand-review the disagreements plus a 50-case spot check (**Rebecca, about 1–2 hours**).
4. **Rebecca approves** the new Supabase tables (a schema change).
5. Run Jev and Decisions on motion text with the outcomes hidden. Compare accuracy, calibration and cost, and pick a winner.
6. Treat scores as a research signal, not legal advice.
