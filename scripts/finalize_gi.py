import json,collections,datetime
C=collections.Counter
D=json.load(open("cases/index.json"));idx=D["cases"];R=json.load(open("raw_labels.json"))
OUTS={"granted","denied","granted_in_part","not_reached"};CTS={"flsa","state_wage_hour","title_vii","ada","adea","erisa","warn","other"}
ok=lambda v,s:(v or "").lower() if (v or "").lower() in s else None
L=[]
for c in idx:
    r=R[c["id"]];d=ok(r["decisions"].get("out"),OUTS);j=ok(r["jev"].get("out"),OUTS);h=ok(r["heuristic"],OUTS)
    dc=ok(r["decisions"].get("ct"),CTS);jc=ok(r["jev"].get("ct"),CTS);ag=bool(d and d==j)
    L.append({"id":c["id"],"case_name":c["case_name"],"court":c["court"],"date_filed":c["date_filed"],"url":c["source_url"],"pdf_url":c["pdf_url"],
      "source":"govinfo","source_case_key":c["package_id"],"docket_id":None,"search_bucket":c["search_bucket"],"decisions_outcome":d,"jev_outcome":j,
      "heuristic_outcome":h,"decisions_claim_type":dc,"jev_claim_type":jc,"claim_type":dc if dc==jc else None,"outcome_final":d if ag else None,
      "label_status":"auto_accepted" if ag else "review","dispositive_excerpt":r["dispositive_excerpt"] or None,"docket_text":c.get("docket_text")})
json.dump(L,open("../labels_batch2_govinfo.json","w"),indent=1)
q=lambda v:"NULL" if v is None else "'"+str(v).replace("'","''")+"'"
TS="2026-10-11T16:50:00-04:00";RD="2026-10-11-b2-govinfo-decisions";RJ="2026-10-11-b2-govinfo-jev"
s=[f"""-- 005_load_employment_12b6_batch2.sql — NOT APPLIED. Batch 2: {len(L)} rulings from GovInfo USCOURTS (not CourtListener).
-- Post-003a names (model_runs, decisions_outcome, not_reached, lowercase claim_type). Apply AFTER 004.
-- One row per lawsuit: cases.source='govinfo', docket_id NULL (it is a CourtListener id), lawsuit key = GovInfo packageId
-- in new column cases.source_case_key (unique per source). Idempotent: guarded ALTER + ON CONFLICT DO NOTHING.
-- DRY RUN: replace the final COMMIT with ROLLBACK.
BEGIN;
ALTER TABLE litigation.cases ADD COLUMN IF NOT EXISTS source_case_key text;
COMMENT ON COLUMN litigation.cases.source_case_key IS 'Lawsuit id in the source system, e.g. GovInfo packageId USCOURTS-moed-4_23-cv-00769. CourtListener rows use docket_id.';
CREATE UNIQUE INDEX IF NOT EXISTS cases_source_case_key_unique ON litigation.cases(source, source_case_key) WHERE source_case_key IS NOT NULL;
INSERT INTO litigation.model_runs(run_id,tool,model,stage,started_at,notes) VALUES
('{RD}','decisions','gpt-6-luna','outcome_label','{TS}','batch2 govinfo label_gi.py'),
('{RJ}','jev','jev-1.13.0','outcome_label','{TS}','batch2 govinfo label_gi.py') ON CONFLICT DO NOTHING;"""]
for o in L:
    s.append(f"INSERT INTO litigation.cases(case_id,case_name,court,docket_id,claim_type,class_vehicle,search_bucket,source,source_case_key) VALUES ({q(o['id'])},{q(o['case_name'])},{q(o['court'])},NULL,{q(o['claim_type'])},'unknown',{q(o['search_bucket'])},'govinfo',{q(o['source_case_key'])}) ON CONFLICT DO NOTHING;")
    s.append(f"INSERT INTO litigation.motions(motion_id,case_id,motion_text_free) VALUES ({q(o['id']+'-m1')},{q(o['id'])},false) ON CONFLICT DO NOTHING;")
    s.append(f"INSERT INTO litigation.rulings(ruling_id,motion_id,date_filed,opinion_url,dispositive_excerpt,decisions_outcome,jev_outcome,heuristic_outcome,decisions_claim_type,jev_claim_type,outcome_final,label_status,decisions_run_id,jev_run_id,labeled_at) VALUES ({q(o['id']+'-r1')},{q(o['id']+'-m1')},{q(o['date_filed'])},{q(o['url'])},{q(o['dispositive_excerpt'] or o['docket_text'])},{q(o['decisions_outcome'])},{q(o['jev_outcome'])},{q(o['heuristic_outcome'])},{q(o['decisions_claim_type'])},{q(o['jev_claim_type'])},{q(o['outcome_final'])},{q(o['label_status'])},'{RD}','{RJ}','{TS}') ON CONFLICT DO NOTHING;")
s.append(f"SELECT source,count(*) FROM litigation.cases GROUP BY 1; -- expect govinfo={len(L)}\nCOMMIT;\n")
open("../../supabase/005_load_employment_12b6_batch2.sql","w").write("\n".join(s))
ag=sum(o["decisions_outcome"]==o["jev_outcome"] for o in L);cag=sum(o["decisions_claim_type"]==o["jev_claim_type"] for o in L)
print(len(L),"agree",ag,"ct agree",cag,"final",C(o["outcome_final"] for o in L),"dec",C(o["decisions_outcome"] for o in L),"ct",C(o["claim_type"] for o in L))
