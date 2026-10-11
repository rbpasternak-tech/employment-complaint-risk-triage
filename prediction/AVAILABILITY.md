# Prediction / risk-triage data availability (Oct 11, 2026, ~5:15 PM ET)

## Blockers
- **CourtListener API: blocked.** HTTP 429, retry-after ≈ 14,866 s from 4:57 PM, so it resets around **9:05 PM ET**. The batch-2 harvest (PIDs 623406/623409) is still sleeping on it; I left it alone.
- **courtlistener.com docket HTML: blocked** for both the box and WebFetch (CloudFront 403).
- **What worked (free, no API quota):** the Internet Archive RECAP mirror (`archive.org` items `gov.uscourts.<court>.<pacer_id>`, found via advancedsearch by title + court). It gives the file list for each case, and I downloaded the PDFs from `storage.courtlistener.com/recap/...`, which is public S3 storage, not the rate-limited API.
- **GovInfo USCOURTS has opinions only.** None of the batch-2 packages contain complaints or motions.

## Count (of 28 dashboard cases plus 4 extra FLSA cases found by web search)
- Matched to a RECAP/IA docket: 24 of 28. No IA item for e02, e05, e12, e13, g09; g08 has no complaint.
- **Complaint free (a): 19 matters downloaded** (15 of the 28 plus x2, x3, x4 and g05). Dropped: e01, e09, e11, g10, g08 (no complaint PDF); g05 is kept but has no outcome.
- **Complaint + motion (a+b): 6** by the heuristic typer (g01, g11, g12, g13, x3, e03). g13-doc63 looks like an NDNY decision (APPEARANCES block), and g12-doc9 is a pre-motion letter, so the reliable count is about 4. Motion PDFs exist in most other folders but didn't pass the type/date filter. **a+b+c: 1** (x3); g00 and x4 have oppositions without a matched motion.
- **Outcome confirmed independently: 13** (10 from GovInfo docket summaries, 3 from opinion text: x2, x3, x4). 5 batch-1 matters have tool-agreement outcomes only (UNCONFIRMED). 1 (g05) has no outcome.

| matter | case | court | outcome_final | outcome source | operative complaint (filed) | motion | opp | ruling PDF |
|---|---|---|---|---|---|---|---|---|
| g00 | Devillaz v. Atmosphere Gastropub, Inc. et al | cod | granted_in_part | govinfo_docket_summary | g00-doc50 (2022-11-28) | — | yes | yes |
| g01 | Seguin v. Royal Highness, LLC et al | mied | granted | govinfo_docket_summary | g01-doc1 (2024-10-11) | yes | — | — |
| g02 | Kluender, Michelle v. Oak Grove Assisted Care | wiwd | denied | govinfo_docket_summary | g02-doc1 (2023-04-26) | — | — | — |
| g03 | Rivera v. CHSPSC, LLC | nmd | denied | govinfo_docket_summary | g03-doc1 (2023-04-19) | — | — | yes |
| g04 | Jenkins, on behalf of himself and all similar | ohsd | granted_in_part | govinfo_docket_summary | g04-doc7 (2023-08-03) | — | — | — |
| g06 | McCarthy v. Medicus Healthcare Solutions, LLC | nhd | denied | govinfo_docket_summary | g06-doc1 (2021-08-12) | — | — | — |
| g11 | Garland v. Duane Morris, LLP et al | casd | granted_in_part | govinfo_docket_summary | g11-doc1 (2024-07-31) | yes | — | — |
| g12 | Timberg v. Toombs et al | nyed | granted_in_part | govinfo_docket_summary | g12-doc1 (2020-12-12) | yes | — | — |
| g13 | Mizzero v. Albany Med Health System | nynd | denied | govinfo_docket_summary | g13-doc62 (2024-09-24) | yes | — | — |
| g14 | Latipov et al v. AN Enterprise Inc et al | ilnd | denied | govinfo_docket_summary | g14-doc1 (2023-03-24) | — | — | yes |
| x2 | Featherstone v. FCA US, LLC | mied | denied | opinion_text | x2-doc25 (2023-06-05) | — | — | — |
| x3 | Van Duser v. Tozzer Ltd. | nysd | denied | opinion_text | x3-doc1 (0000-00-00) | yes | yes | — |
| x4 | Preston v. World Travel Holdings, Incorporate | mad | denied | opinion_text(ECF 43 in folder) | x4-doc1 (2023-10-16) | — | yes | yes |
| e00 | Harrington v. Fb Hospitality, LLC | dcd | denied | tool_agreement_UNCONFIRMED | e00-doc1 (2022-03-14) | — | — | yes |
| e03 | Slaughter v. Catholic University of America | dcd | granted | tool_agreement_UNCONFIRMED | e03-doc1 (2023-09-15) | yes | — | yes |
| e07 | Cruz v. Jimenez Construction LLC | dcd | granted_in_part | tool_agreement_UNCONFIRMED | e07-doc1 (2020-07-21) | — | — | yes |
| e08 | Owens v. Thompson | dcd | denied | tool_agreement_UNCONFIRMED | e08-doc1 (2023-03-10) | — | — | yes |
| e10 | Covington v. Fmc & Associates, LLC | dcd | denied | tool_agreement_UNCONFIRMED | e10-doc1 (2022-05-23) | — | — | yes |
| g05 | Cayton v. Metropolitan Government of Nashvill | tnmd | — | — | g05-doc1 (0000-00-00) | — | — | — |

Files: `cases/<matter>/*.pdf|.txt`, `cases/manifest.json` (matters with outcome and source), `cases/manifest_raw.json` (every doc with source_url and heuristic type), `cases/filings.json` (34 rows: filing_id, matter_id, filing_kind, path, source_url, filed). filings.json passes `framework/loaders.complaints` (19 complaints, no leakage error). Rulings are marked `filing_kind=ruling`.

## Caveats
- The doc typer is regex-based. Motion and opposition tags need a human glance (for example, g12-doc9 is a pre-motion letter).
- The operative complaint is the latest complaint filed before the ruling. For x3 the operative amended complaint (Dkt 39) is a scan with no text, so doc1 is used. For e00 the 2024 ruling may address a later amended complaint that isn't in the folder.
- Ruling dates for x2 and x3 are approximate (2024).

## Risk signals to extract (complaint only)
class_vehicle (FLSA collective / Rule 23 / both / none) · claim_type · factual_specificity (named hours, pay rates, dates, comparators vs boilerplate) · plaintiff_firm (regex on the signature block, not the model) · court/circuit · plaintiff_count bucket (named + opt-ins) · damages_pled (specific $ vs unspecified) · amended vs original · joint-employer and arbitration mentions.

## Test design
1. Input: the operative complaint text only (`complaints` loader; rulings and motions are refused). Motion text is an optional second arm.
2. Tools: Decisions (gpt-6-luna), Jev (jev-1.13.0) and a reasoning-model baseline each output `predicted_outcome` ∈ granted / denied / granted_in_part plus `p_survive`, and the features above (config.feature_extraction.json, config.risk_score.json).
3. Ground truth: `claims_survived` = outcome_final ∈ (denied, granted_in_part). Score only on the 13 independently confirmed matters; report the 5 UNCONFIRMED ones separately.
4. Metrics: accuracy on 3-way outcome, Brier score / AUC on p_survive, cost per 1k complaints, latency, and agreement among the three tools.
5. Leakage checks: no ruling text, the date filter, and the loader's LEAK_MARKERS guard. Strip any reference to later orders in amended complaints.

## Recommendation
Run the triage proof of concept now on the 13 confirmed matters (n is small, so this is a smoke test). Grow to 50+ through the IA mirror: search IA titles for FLSA/NYLL collective actions whose 12(b)(6) outcome is known from GovInfo docket summaries. That needs no CourtListener quota and nothing purchased from PACER. Once the API resets after ~9:05 PM, use docket-entries to confirm doc types and ruling dates.
