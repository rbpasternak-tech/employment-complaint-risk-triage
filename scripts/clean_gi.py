import json,collections
C=collections.Counter
L={o["id"]:o for o in json.load(open("../labels_batch2_govinfo.json"))}
DROP={"g07":"claim_type other (antitrust class action)","g25":"service-of-process ruling; individual suit"}
for i in range(15,28):
    k=f"g{i:02d}"; DROP.setdefault(k,"individual suit; no class/collective allegations in opinion")
MAG={"g10"}  # g18,g20,g22 are also R&Rs but were dropped as individual suits
# outcome confirmed from GovInfo docket summary (docketText), read by hand
DOCK={"g00":"granted_in_part","g01":"granted","g02":"denied","g03":"denied","g04":"granted_in_part","g06":"denied","g08":"denied",
      "g09":"granted","g11":"granted_in_part","g12":"granted_in_part","g13":"denied","g14":"denied"}
keep=[];dropped=[]
for k,o in L.items():
    if k in DROP: dropped.append({"id":k,"case_name":o["case_name"],"reason":DROP[k]}); continue
    o=dict(o); o["is_magistrate_rr"]=k in MAG; o["label_status"]="review"
    o["outcome_final"]=None if k in MAG else DOCK.get(k); o["outcome_final_source"]="govinfo_docket_summary" if o["outcome_final"] else None
    notes=[]
    if k in MAG: notes.append("Magistrate report and recommendation, not a final ruling; outcome_final left NULL.")
    if o["outcome_final"] and (o["decisions_outcome"]!=o["outcome_final"] or o["jev_outcome"]!=o["outcome_final"]):
        notes.append(f"Tools wrong vs docket summary: decisions={o['decisions_outcome']}, jev={o['jev_outcome']}, docket={o['outcome_final']}.")
    if k=="g04": notes.append("Docket text concatenates entries; the cited order is on a motion for judgment on the pleadings (12(c)).")
    if k not in MAG and not o["outcome_final"]: notes.append("Docket summary does not state the outcome; unconfirmed.")
    o["review_note"]=" ".join(notes) or None
    keep.append(o)
json.dump(keep,open("labels.json","w"),indent=1); json.dump(keep,open("../labels_batch2_govinfo.json","w"),indent=1)
json.dump(dropped,open("dropped.json","w"),indent=1)
q=lambda v:"NULL" if v is None else ("true" if v is True else "false" if v is False else "'"+str(v).replace("'","''")+"'")
TS="2026-10-11T16:50:00-04:00";RD="2026-10-11-b2-govinfo-decisions";RJ="2026-10-11-b2-govinfo-jev"
s=[f"""-- 005_load_employment_12b6_batch2.sql — NOT APPLIED. Apply AFTER 004. Batch 2: {len(keep)} rulings from GovInfo USCOURTS (not CourtListener).
-- Cleaned Oct 11, 2026: dropped {len(dropped)} non-class/collective or off-topic rulings (see batch2/gi/dropped.json).
-- Post-003a names. One row per lawsuit: cases.source='govinfo', docket_id NULL (CourtListener id), lawsuit key = GovInfo packageId in cases.source_case_key.
-- outcome_final is set ONLY where confirmed from the GovInfo docket summary (rulings.outcome_final_source='govinfo_docket_summary'); tool agreement never sets it.
-- All rows label_status='review'. Idempotent: guarded ALTERs + ON CONFLICT DO NOTHING. DRY RUN: replace final COMMIT with ROLLBACK.
BEGIN;
ALTER TABLE litigation.cases   ADD COLUMN IF NOT EXISTS source_case_key text;
ALTER TABLE litigation.rulings ADD COLUMN IF NOT EXISTS outcome_final_source text;
ALTER TABLE litigation.rulings ADD COLUMN IF NOT EXISTS is_magistrate_rr boolean NOT NULL DEFAULT false;
ALTER TABLE litigation.rulings ADD COLUMN IF NOT EXISTS review_note text;
COMMENT ON COLUMN litigation.cases.source_case_key IS 'Lawsuit id in the source system, e.g. GovInfo packageId. CourtListener rows use docket_id.';
COMMENT ON COLUMN litigation.rulings.outcome_final_source IS 'Independent source confirming outcome_final, e.g. govinfo_docket_summary, human. NULL = unconfirmed.';
COMMENT ON COLUMN litigation.rulings.is_magistrate_rr IS 'Magistrate judge report and recommendation, not a final ruling.';
CREATE UNIQUE INDEX IF NOT EXISTS cases_source_case_key_unique ON litigation.cases(source, source_case_key) WHERE source_case_key IS NOT NULL;
INSERT INTO litigation.model_runs(run_id,tool,model,stage,started_at,notes) VALUES
('{RD}','decisions','gpt-6-luna','outcome_label','{TS}','batch2 govinfo label_gi.py'),
('{RJ}','jev','jev-1.13.0','outcome_label','{TS}','batch2 govinfo label_gi.py') ON CONFLICT DO NOTHING;"""]
for o in keep:
    s.append(f"INSERT INTO litigation.cases(case_id,case_name,court,docket_id,claim_type,class_vehicle,search_bucket,source,source_case_key) VALUES ({q(o['id'])},{q(o['case_name'])},{q(o['court'])},NULL,{q(o['claim_type'])},'unknown',{q(o['search_bucket'])},'govinfo',{q(o['source_case_key'])}) ON CONFLICT DO NOTHING;")
    s.append(f"INSERT INTO litigation.motions(motion_id,case_id,motion_text_free) VALUES ({q(o['id']+'-m1')},{q(o['id'])},false) ON CONFLICT DO NOTHING;")
    s.append(f"INSERT INTO litigation.rulings(ruling_id,motion_id,date_filed,opinion_url,dispositive_excerpt,decisions_outcome,jev_outcome,heuristic_outcome,decisions_claim_type,jev_claim_type,outcome_final,outcome_final_source,is_magistrate_rr,review_note,label_status,decisions_run_id,jev_run_id,labeled_at) VALUES ({q(o['id']+'-r1')},{q(o['id']+'-m1')},{q(o['date_filed'])},{q(o['url'])},{q(o['dispositive_excerpt'] or o['docket_text'])},{q(o['decisions_outcome'])},{q(o['jev_outcome'])},{q(o['heuristic_outcome'])},{q(o['decisions_claim_type'])},{q(o['jev_claim_type'])},{q(o['outcome_final'])},{q(o['outcome_final_source'])},{q(o['is_magistrate_rr'])},{q(o['review_note'])},'review','{RD}','{RJ}','{TS}') ON CONFLICT DO NOTHING;")
s.append(f"SELECT source,count(*) FROM litigation.cases GROUP BY 1; -- expect govinfo={len(keep)}\nCOMMIT;\n")
open("../../supabase/005_load_employment_12b6_batch2.sql","w").write("\n".join(s))
g=[o for o in keep if o["outcome_final"]]
print(len(keep),"dropped",len(dropped),"agree",sum(o["decisions_outcome"]==o["jev_outcome"] for o in keep),
 "final",C(o["outcome_final"] for o in keep),"dec",C(o["decisions_outcome"] for o in keep),
 "accD",sum(o["decisions_outcome"]==o["outcome_final"] for o in g),"accJ",sum(o["jev_outcome"]==o["outcome_final"] for o in g),len(g))
for o in keep:
  if o["review_note"]: print(o["id"],o["review_note"])
