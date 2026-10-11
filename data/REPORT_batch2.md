# Batch 2 (GovInfo): employment 12(b)(6) rulings, 2022–2026
Generated 2026-10-11 ~4:55 PM ET. Source: GovInfo USCOURTS collection (api.govinfo.gov, DEMO_KEY, ~1.5 s between calls). No CourtListener calls; the running CL harvest (batch2/harvest.py) was not touched.
Caselaw Access Project skipped: its static.case.law data ends around 2018 and has no 2022–2026 district opinions.

## Pull
Query: `"motion to dismiss" AND "12(b)(6)" AND (collective action | putative class | class action | similarly situated)` + claim-type term, 2022-01-01 to 2026-10-01, district courts only, one opinion per lawsuit (GovInfo packageId), batch-1 names excluded.
Hits: flsa 616, state_wage_hour 547, title_vii 2093, adea 485, ada 679. Taken: 8/7/5/4/4 = **28 lawsuits, 28 rulings**, 24 courts. Text = pdftotext of the opinion PDF (`gi/cases/gNN.txt`).

## Labels (Decisions gpt-6-luna vs Jev jev-1.13.0, label.py prompts)
- Outcome agreement: **27/28 (96%)**; claim-type agreement 22/28 (79%)
- Decisions: granted 10, granted_in_part 8, denied 7, not_reached 3
- Final (agreed): granted 9, granted_in_part 8, denied 7, not_reached 3; 1 needs review (g26)
- Disagreement: g26 Nunez-Renck (Decisions granted, Jev granted_in_part) — docket text says granted.

## Problems / review list
- Keyword search is loose: several Title VII / ADEA / ADA hits are individual suits that only mention "class action"; g07 Herzog is an antitrust class action (both tools say claim_type other); g25 Spann is mainly a service-of-process ruling. Consider excluding claim_type=other.
- Likely mislabels vs GovInfo docket text: g04 Jenkins (docket: granted in part; both tools said not_reached), g08 Taylor v. Amazon (MTD denied + stay; tools said not_reached).
- Several are magistrate R&Rs (g10, g18, g20, g22), not final rulings.
- docket_id is NULL for these (it is a CourtListener id); lawsuit key is the new `cases.source_case_key` (GovInfo packageId).

## Files
- `gi/harvest_gi.py`, `gi/label_gi.py`, `gi/finalize_gi.py`, `gi/cases/` (PDF + text + index.json), `gi/raw_labels.json`, `labels_batch2_govinfo.json`
- `../supabase/005_load_employment_12b6_batch2.sql` — idempotent, post-003a names, guarded ALTER adds `cases.source_case_key` + unique index on (source, source_case_key); rows have source='govinfo'. **Not applied.** Apply after 004.

## Cleanup (Oct 11, 2026 4:55 PM ET) — supersedes the counts above
- Dropped 14 (batch2/gi/dropped.json): g07 Herzog (antitrust, claim_type other), g25 Spann, and g15–g27 individual suits with no class/collective allegations (incl. magistrate R&Rs g18, g20, g22, so only g10 remains flagged).
- Kept **14 rulings / 14 lawsuits**. All label_status='review'; tool agreement no longer sets anything.
- outcome_final set only from the GovInfo docket summary (outcome_final_source='govinfo_docket_summary') for 12; NULL for g05 (summary silent) and g10 (magistrate R&R, is_magistrate_rr=true).
- Confirmed outcomes: denied 6, granted_in_part 4, granted 2. Decisions vs Jev agreement 14/14; accuracy vs confirmed: Decisions 9/12, Jev 9/12 (both wrong on g00, g04, g08; see review_note).
- 005 adds guarded columns: cases.source_case_key, rulings.outcome_final_source, rulings.is_magistrate_rr, rulings.review_note.
