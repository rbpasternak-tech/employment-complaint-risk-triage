Build a polished, interactive **React artifact**: a dashboard for my proof of concept, "Employment Complaint Risk Triage". Use the attached **data.json** as the only data source. Embed it in the artifact as a constant; don't fetch anything.

**Purpose and audience.** I'm an employment lawyer. Inbound complaints and demand letters are surging because AI makes them cheap to produce. I'm testing whether cheap classifiers, the **Decisions API** (gpt-6-luna) and **Jev** (jev-1.13.0), can triage that flood. A reasoning model (GPT or Claude) is the planned baseline. "Risk" is grounded in real outcomes: did any claim survive a Rule 12(b)(6) motion to dismiss? The audience is law-firm colleagues and practice leaders, not engineers. Use plain language and define terms on hover.

**Sections**
1. **Overview KPIs:** rulings, lawsuits, outcome agreement between the tools, claim-type agreement, rulings with a confirmed outcome, and accuracy for each tool, shown as "10 of 13" rather than only as a percentage.
2. **Tool scorecard:** Decisions vs Jev vs Baseline, with accuracy, agreement, cost per 1,000 docs and median latency. Baseline (gpt-6.1-sol) has risk scores only, no outcome labels.
3. **Outcome mix:** a chart of outcomes (granted, denied, granted in part, not reached) by claim type, with a toggle between Decisions, Jev and the confirmed outcome.
4. **Case explorer:** a searchable, sortable table with filters for source, court, claim type, outcome, "tools disagree" and "has confirmed outcome". A row expands to show the review note and links to the opinion and PDF.
5. **Disagreements and misses:** cases where the tools disagree, or where either tool differs from outcome_final, each with its review note.
6. **Cost calculator:** inputs for docs per month (default 10,000) and tokens per doc. Show the monthly cost of each tool, using summary.tools usd_per_1k_docs and tools_meta prices, plus the Jev vs Decisions savings.
7. **Complaint risk vs outcome (Phase 1):** use the risk_scores.schema to show an empty-state preview of the planned columns: tool, tier, p_survive and signals. If rows exist, render tier badges and a "risk tier vs actual outcome" matrix.
8. **Methodology:**
   - Sources: CourtListener for batch 1 and GovInfo US Courts Opinions for batch 2, filtered to employment class or collective actions with a 12(b)(6) ruling.
   - Data is stored in Supabase.
   - Classification is done by the Decisions API and Jev, given the same prompt and label set.
   - outcome_final comes from the court docket or a human review.
   - Planned next steps: complaint-only inputs, the baseline, and other outcomes (class certification, MSJ, settlement).

**Required caveat.** Put it in a visible banner at the top and again in Methodology: *"Current labels are outcome labels. The tools read the ruling itself, so this measures reading accuracy and cost, not prediction. Phase 1 risk scores from complaint text alone are now included (risk_scores): on this small, survival-heavy sample all tools rated nearly every complaint high, so they have not yet shown they can separate strong from weak complaints."* Also state that the sample is small (28 rulings, 13 confirmed) and the results are directional only.

**Style.** Professional and restrained, like a law-firm memo or financial dashboard. Use a neutral palette with one accent color, and the same color for each tool across every chart. Use clean typography, a responsive layout and accessible contrast. No emojis, and no playful copy. Use Recharts for the charts and Tailwind for styling. Handle nulls gracefully. Per-ruling per_call metrics exist only for e00, so take cost and latency from summary.tools.
