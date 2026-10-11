# Prompts for your Supabase-connected Claude project

Run them in this order: **004 (done) → 005 → 006 → 007**. For each one, attach the file, paste the prompt, check the dry run, then reply "go".

## 1. 005: load batch 2
Attach `supabase/005_load_employment_12b6_batch2.sql`.
```
Run the attached 005_load_employment_12b6_batch2.sql against Supabase project yhaahsrevxueogdwxxtl, in two steps.
1. Dry run: run it inside BEGIN … ROLLBACK (swap the final COMMIT for ROLLBACK). Inside the transaction, show:
   select source, count(*) from litigation.cases group by 1;
   select count(*) from litigation.rulings;
   select docket_id, count(*) from litigation.cases group by 1 having count(*)>1;  -- expect no rows
   Stop and show me before applying.
2. After I say go: apply it as migration "005_load_employment_12b6_batch2" and rerun those three queries.
Only touch the litigation schema. Don't touch legal_ingest or public, and don't run 003b.
```

## 2. 006: dashboard views (read-only)
Attach `supabase/006_dashboard_views.sql`.
```
Run the attached 006_dashboard_views.sql against yhaahsrevxueogdwxxtl. It only creates views.
1. Dry run inside BEGIN … ROLLBACK. Inside the transaction, show: select * from litigation.tool_summary; and select count(*) from litigation.tool_comparison;
2. After I say go: apply it as migration "006_dashboard_views" and rerun both queries. Confirm the views exist with security_invoker=true.
Litigation schema only.
```

## 3. 007: triage schema
Attach `supabase/007_triage_schema.sql`. Keep `007_rollback.sql` handy.
```
Run the attached 007_triage_schema.sql against yhaahsrevxueogdwxxtl. It creates a new schema, triage, and links it to litigation without moving any data.
1. Dry run inside BEGIN … ROLLBACK. Inside the transaction, show:
   select count(*) from litigation.cases;   and   select count(*) from triage.matters;   -- should be equal
   select * from triage.outcomes limit 5;
   select table_name from information_schema.tables where table_schema='triage';  -- matters, filings, features, risk_scores
   select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid='litigation.model_runs'::regclass;
   Also report any error, especially about the model_runs check-constraint names.
   Stop and show me before applying.
2. After I say go: apply it as migration "007_triage_schema", rerun the queries, and confirm RLS is on for all four triage tables and that anon and authenticated have no grants on triage.
Don't touch legal_ingest or public, and don't run 003b. If anything fails, run the attached 007_rollback.sql.
```
Note: 007 drops and recreates the `model_runs` tool and stage checks. They may still have the names from before 003a (`label_runs_*_check`). The script handles both names, but if the dry run finds a third name, ask Claude to tell you what it is before you say go.

## Ask Dots
1. Does anything you run (scripts, triggers, edge functions, cron jobs) refer to `legal_ingest` tables or columns by their current names? 003b renames them and recreates the trigger functions.
2. Is it OK if I apply 003b, and when? Will you rerun your pipeline afterward to check it?
3. Do you plan to pull court filings (complaints, demand letters) into `legal_ingest`? If so, we'll feed `triage.filings` from a view of your tables rather than both of us writing the same data.
4. Do you want `triage` to stay hands-off for your pipeline (my scripts write it, you only read)?
