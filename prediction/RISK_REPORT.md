# Phase 1: Complaint risk scoring vs. 12(b)(6) outcomes

*Run Oct 11, 2026 (ET). Employment Complaint Risk Triage. Source data: `prediction/risk_results.json`.*

## Summary for lawyers

We gave three AI tools **only the complaint**, with no motion, ruling or docket, and asked each to predict whether **at least one claim would survive a Rule 12(b)(6) motion to dismiss** (survived = motion denied, or granted only in part).

- **All three tools rated essentially every complaint "high risk" (likely to survive).** Decisions and Jev rated 19 of 19 high. The GPT baseline rated 18 high and 1 medium.
- On the **13 cases with independently confirmed outcomes**, each tool was "right" **12 of 13 (92%)**. But 12 of those 13 complaints actually survived, so a rule that just says "always survives" scores the same 92%. **The tools have not yet shown they can tell a strong complaint from a weak one.** The one confirmed dismissal (Seguin v. Royal Highness, granted in full) was rated high by all three.
- On calibration (Brier score, lower is better), none beat the naive base rate on the 13 confirmed cases (Decisions 0.072, Jev 0.071, baseline 0.075 vs. 0.071 for "always survives").
- **The only real signal:** the GPT baseline flagged Slaughter v. Catholic University (e03) as medium, 0.50, and that case was dismissed (unconfirmed outcome). It did so because the document we fed it was a notice of removal with no facts, not the complaint itself.
- **Cost per 1,000 complaints** (features + risk score): Decisions **$1.68**, Jev **$0.78**, GPT baseline **$18.74** (risk only). Median latency: about 253 ms, 237 ms, and 7.3 s.

**Bottom line:** the pipeline works end to end, cheaply and without leakage. But this sample is far too small and too survival-heavy (published 12(b)(6) fights over FLSA collective actions mostly survive) to test whether the scores discriminate. The next step is a sample with many more dismissals, plus prompts that force a spread of tiers or rank complaints against each other.

## Methods

**Inputs.** 19 operative complaints from the free Internet Archive RECAP mirror, with no PACER purchases (`cases/filings.json`, loaded with `framework/loaders.complaints`). The loader accepts only complaint, amended-complaint and demand-letter filings, refuses rulings and motions, and runs a leakage guard (`LEAK_MARKERS`: "IT IS ORDERED", "motion to dismiss is GRANTED/DENIED", "MEMORANDUM OPINION", "REPORT AND RECOMMENDATION"). No complaint tripped it. Text was capped at 60,000 characters (first 52k + last 8k when longer, keeping facts, counts, prayer and signature block). Three complaints hit the cap.

**Stage 1: feature extraction (Decisions and Jev, same questions, multiple choice).** Class vehicle (FLSA collective / Rule 23 / both / individual), primary claim type, factual specificity (specific / mixed / boilerplate), named-plaintiff count bucket, damages pled, and arbitration mentioned (yes/no probability). Court came from the docket metadata. Plaintiff firm came from a regex on the signature block, not a model. Arbitration was also checked by keyword.

**Stage 2: risk score.**
- *Decisions and Jev:* two questions. (a) Yes/no probability: "Reading only this complaint, would at least some claims likely survive a Rule 12(b)(6) motion?", which gives p_survive. (b) Multiple choice for the tier: high (very likely at least one claim survives), medium (uncertain), low (likely dismissed in full). They return choices and probabilities only, with no rationale.
- *GPT baseline:* `gpt-6.1-sol` (strongest current OpenAI model available to the key) via the Responses API, medium reasoning effort, strict JSON output. Prompted as an employment-defense litigator to weigh class vehicle, claim types, factual specificity (hours, pay rates, comparators), circuit pleading standards (e.g. 2d Cir. Lundy/Dejesus), joint-employer theories, arbitration and counsel. Returns tier, p_survive, a rationale of 60 words or fewer, and signals.

**Ground truth.** `outcome_final` from `cases/manifest.json`. **Primary scoring: 13 matters with independent confirmation** (10 GovInfo docket summaries, 3 opinion text). Secondary: all 18 with a known outcome, including 5 whose outcome comes only from the Phase 0 tool-agreement labels (UNCONFIRMED). g05 (Cayton) has no outcome and is scored but not graded.

**Metrics.** Accuracy of "high" vs. "not high" against survived. Confusion table. Brier score on p_survive. Cost at list input prices (Decisions $0.10/M, Jev $0.042/M, GPT-6.1 Sol $2/M input + $10/M output). Wall-clock latency.

## Results

### Primary: 13 independently confirmed outcomes (12 survived, 1 dismissed)
| Tool | Accuracy (high vs not) | High / Med / Low | Confusion: high&survived · high&dismissed · not-high&survived · not-high&dismissed | Mean p_survive | Brier |
|---|---|---|---|---|---|
| Decisions (gpt-6-luna) | 92% (12/13) | 13 / 0 / 0 | 12 · 1 · 0 · 0 | 0.87 | 0.072 |
| Jev (jev-1.13.0) | 92% (12/13) | 13 / 0 / 0 | 12 · 1 · 0 · 0 | 0.84 | 0.071 |
| GPT baseline (gpt-6.1-sol) | 92% (12/13) | 13 / 0 / 0 | 12 · 1 · 0 · 0 | 0.91 | 0.075 |
| Naive "always survives" | 92% | all high | | 0.92 | 0.071 |

### Secondary: all 18 known outcomes (16 survived, 2 dismissed; 5 unconfirmed)
| Tool | Accuracy (high vs not) | High / Med / Low | Confusion: high&survived · high&dismissed · not-high&survived · not-high&dismissed | Mean p_survive | Brier |
|---|---|---|---|---|---|
| Decisions (gpt-6-luna) | 89% (16/18) | 18 / 0 / 0 | 16 · 2 · 0 · 0 | 0.87 | 0.058 (n=17) |
| Jev (jev-1.13.0) | 89% (16/18) | 18 / 0 / 0 | 16 · 2 · 0 · 0 | 0.84 | 0.079 |
| GPT baseline (gpt-6.1-sol) | 94% (17/18) | 17 / 1 / 0 | 16 · 1 · 0 · 1 | 0.90 | 0.069 |
| Naive "always survives" | 89% | all high | | 0.89 | 0.099 |

### Cost and speed (all 19 complaints)
| Tool | Total cost (19) | Per 1,000 complaints | Median latency (risk call) |
|---|---|---|---|
| Decisions (gpt-6-luna) | $0.032 | $1.68 | 253 ms |
| Jev (jev-1.13.0) | $0.015 | $0.78 | 237 ms |
| GPT baseline (gpt-6.1-sol) | $0.356 | $18.74 | 7310 ms |

Decisions and Jev costs include both stages (features + risk). The baseline did risk only.

### Where the tools disagree
- **Risk tier:** only e03 (Slaughter): Decisions high (no p_survive returned), Jev high 0.65, baseline medium 0.50.
- **Features:** Decisions vs. Jev disagreed mainly on factual specificity. Jev called 6 complaints "specific" where Decisions said "mixed" (g01, g11, g14, x2, x4, e07). They also split on claim type for g14 (FLSA vs. state wage-hour) and on damages for e03. Class vehicle, plaintiff count and arbitration matched on every complaint.
- No complaint mentioned arbitration in a way either tool flagged.

## Per-case results
| Matter | Case | Court | Outcome | Confirmed | Class vehicle | Specificity | Decisions | Jev | Baseline |
|---|---|---|---|---|---|---|---|---|---|
| g00 | Devillaz v. Atmosphere Gastropub, Inc. et al | COD | granted_in_part | yes | both | mixed | high 0.85 | high 0.86 | high 0.94 |
| g01 | Seguin v. Royal Highness, LLC et al | MIED | granted | yes | both | mixed | high 0.85 | high 0.79 | high 0.91 |
| g02 | Kluender, Michelle v. Oak Grove Assisted Care LLC | WIWD | denied | yes | both | mixed | high 0.86 | high 0.85 | high 0.85 |
| g03 | Rivera v. CHSPSC, LLC | NMD | denied | yes | both | mixed | high 0.86 | high 0.87 | high 0.88 |
| g04 | Jenkins, on behalf of himself and all similarly situated individuals, v. EVO Services Group, LLC | OHSD | granted_in_part | yes | flsa_collective | mixed | high 0.84 | high 0.74 | high 0.78 |
| g06 | McCarthy v. Medicus Healthcare Solutions, LLC | NHD | denied | yes | flsa_collective | mixed | high 0.93 | high 0.82 | high 0.80 |
| g11 | Garland v. Duane Morris, LLP et al | CASD | granted_in_part | yes | rule23_class | mixed | high 0.79 | high 0.83 | high 0.94 |
| g12 | Timberg v. Toombs et al | NYED | granted_in_part | yes | flsa_collective | mixed | high 0.87 | high 0.84 | high 0.94 |
| g13 | Mizzero v. Albany Med Health System | NYND | denied | yes | both | mixed | high 0.91 | high 0.88 | high 0.95 |
| g14 | Latipov et al v. AN Enterprise Inc et al | ILND | denied | yes | both | mixed | high 0.86 | high 0.82 | high 0.94 |
| x2 | Featherstone v. FCA US, LLC | MIED | denied | yes | both | mixed | high 0.90 | high 0.88 | high 0.94 |
| x3 | Van Duser v. Tozzer Ltd. | NYSD | denied | yes | both | specific | high 0.95 | high 0.91 | high 0.98 |
| x4 | Preston v. World Travel Holdings, Incorporated | MAD | denied | yes | both | mixed | high 0.87 | high 0.87 | high 0.97 |
| e00 | Harrington v. Fb Hospitality, LLC | DCD | denied | no | both | mixed | high 0.90 | high 0.87 | high 0.95 |
| e03 | Slaughter v. Catholic University of America | DCD | granted | no | both | boilerplate | high  | high 0.65 | medium 0.50 |
| e07 | Cruz v. Jimenez Construction LLC | DCD | granted_in_part | no | individual | mixed | high 0.85 | high 0.86 | high 0.94 |
| e08 | Owens v. Thompson | DCD | denied | no | individual | specific | high 0.89 | high 0.84 | high 0.94 |
| e10 | Covington v. Fmc & Associates, LLC | DCD | denied | no | individual | specific | high 0.87 | high 0.87 | high 0.96 |
| g05 | Cayton v. Metropolitan Government of Nashville & Davidson County | TNMD | — | — | flsa_collective | mixed | high 0.86 | high 0.80 | high 0.90 |

## Misses and why
- **g01 Seguin v. Royal Highness (E.D. Mich.), granted in full, confirmed. All three tools: high.** Baseline: "The FLSA tip-retention claim plausibly alleges a specific mandatory pool distributing budtenders’ tips to managers and supervisors, with employment dates, pay rate, duties, and distribution mechanics. Paying above minimum wage does not defeat this prohibition. Managerial-status and commerce allegations have some gaps, and unjust enrichment is vulnerable, but complete dismissal is unlikely." The court evidently found the tip-pool/managerial theory deficient. That is a legal-theory call the tools didn't anticipate, because the complaint is well drafted (McGillivary Steele Elkin) and factually detailed. *Lesson: detailed facts ≠ legally viable theory.*
- **e03 Slaughter v. Catholic University (D.D.C.), granted, UNCONFIRMED.** Decisions and Jev: high. Baseline: medium 0.50, a partial hit. The input was a **notice of removal**, not the complaint (doc-typer error), so no tool saw the pleaded facts.
- **Data issue, g04 Jenkins:** the file used as the "operative complaint" (doc 7) is actually an **answer/counterclaim**. The baseline noticed. The prediction (high; outcome granted in part, which counts as survived) happened to be right for the wrong input.

## Limitations
- **n is tiny.** 13 confirmed cases with only 1 dismissal. One case changes accuracy by about 8 points. Nothing here is statistically meaningful; treat it as a smoke test of the pipeline.
- **Selected data.** The cases come from Phase 0's 12(b)(6) ruling sample and are limited to those with free complaints on the IA/RECAP mirror. They are mostly FLSA collective actions, where survival is common. The sample is not representative of inbound complaints or demand letters, and the base rate here (92%) is far higher than a realistic triage queue.
- **Unconfirmed outcomes.** 5 of the 18 outcomes rest on tool-agreement labels from Phase 0, not an independent source. g05 has no outcome.
- **Input quality.** Two inputs are not the complaint (g04 answer/counterclaim, e03 notice of removal). For e00 the ruling may address a later amended complaint not in the folder, and for x3 the operative amended complaint is a scan with no text, so the original was used.
- **Tier collapse.** Cheap tools return the single most likely choice. With "survives" being the likely answer for almost any professionally drafted complaint, they never pick medium or low. Ranking by p_survive, or forcing relative ranking, is needed.
- **Survival ≠ exposure.** "At least one claim survives" ignores which claims and how much they're worth. A partial grant that guts the class claims still counts as "survived."

## Next steps
1. Build a balanced set: 50+ matters with many full dismissals (GovInfo docket summaries + IA mirror, all free), and fix the doc typer so every input is the true operative complaint.
2. Score per claim, not per complaint, and add a "class/collective claims survive" target.
3. Use p_survive ranking (AUC) and a calibrated threshold rather than the tier label. Try prompts that force a spread.
4. Phase 2: demand letters.

## Files
`prediction/risk_run.py` (runner, keys from env only), `prediction/risk_analyze.py`, `prediction/risk_raw.json`, `prediction/risk_results.json`, `supabase/008_load_risk_scores_phase1.sql` (requires 007, not applied), `claude-pack/data.json` (risk_scores), `dashboard/index.html` ("Complaint risk vs outcome").
