import json,collections,datetime
C=collections.Counter
idx=json.load(open("cases/index.json"));R=json.load(open("raw_labels.json"));RC=json.load(open("recap.json"))
st=json.load(open("state.json"));P={"decisions":0.10,"jev":0.042}
N=lambda v: None if v is None else ("not_reached" if v=="not_decided_on_12b6" else v.lower().replace(" ","_").replace("-","_"))
OUTS={"granted","denied","granted_in_part","not_reached"};CTS={"flsa","state_wage_hour","title_vii","ada","adea","erisa","warn","other"}
ok=lambda v,s: v if v in s else None
cases=[];tok=C();err=C()
for c in idx:
    rc=RC.get(str(c["docket_id"]),{});ops=[]
    for o in c["opinions"]:
        r=R[o["opinion_key"]];d=ok(N(r["decisions"].get("out")),OUTS);j=ok(N(r["jev"].get("out")),OUTS);h=ok(N(r["heuristic"]),OUTS)
        for k in P:
            if "error" in r[k]: err[k]+=1
            else: tok[k]+=r[k].get("tok") or 0
        agree=bool(d and d==j)
        ops.append(o|{"decisions_outcome":d,"jev_outcome":j,"heuristic_outcome":h,"decisions_claim_type":ok(N(r["decisions"].get("ct")),CTS),
          "jev_claim_type":ok(N(r["jev"].get("ct")),CTS),"outcome_final":d if agree else None,"label_status":"model_agreed" if agree else "needs_review",
          "dispositive_excerpt":r["dispositive_excerpt"] or None})
    agreed=[o["decisions_claim_type"] for o in ops if o["decisions_claim_type"] and o["decisions_claim_type"]==o["jev_claim_type"]]
    ct=C(agreed).most_common(1)[0][0] if agreed else (ops[0]["decisions_claim_type"] or ops[0]["jev_claim_type"])
    cases.append({k:c[k] for k in ["id","case_name","court","docket_id","search_bucket"]}|{"claim_type":ct,"recap_mtd_free":rc.get("mtd_free"),"recap_free_docs":rc.get("free_docs"),
      "recap_error":rc.get("error"),"rulings":ops})
json.dump(cases,open("labels.json","w"),indent=1)
rul=[o for c in cases for o in c["rulings"]]
both=[o for o in rul if o["decisions_outcome"] and o["jev_outcome"]]
pct=lambda a,b:f"{a}/{b} ({100*a/b:.0f}%)" if b else "n/a"
ag=sum(o["decisions_outcome"]==o["jev_outcome"] for o in both)
hd=[o for o in rul if o["heuristic_outcome"] and o["decisions_outcome"]];hj=[o for o in rul if o["heuristic_outcome"] and o["jev_outcome"]]
all3=sum(1 for o in rul if o["outcome_final"] and o["outcome_final"]==o["heuristic_outcome"])
rv=[c for c in cases if not c["recap_error"]];free=sum(bool(c["recap_mtd_free"]) for c in rv)
cost={k:tok[k]*P[k]/1e6 for k in P}
md=f"""# Batch 2: employment class/collective-action 12(b)(6) rulings (2018–2025)
Generated {datetime.datetime.now():%Y-%m-%d %H:%M} ET by finalize.py. Source: CourtListener opinions, federal district courts. Values use the post-003a vocabulary.

## Search
Base: `{st and 'see harvest.py BASE'}`. Opinion hits per claim-type query, 2018–2025: {st['counts']}
Pool after district-court filter: {len(st['pool'])} opinions. Batch-1 dockets were excluded, and multiple opinions per docket are grouped into one case (max 3).

## Sample
- Cases (dockets): **{len(cases)}**; rulings (opinions): **{len(rul)}**
- Courts ({len(set(c['court'] for c in cases))}): top {dict(C(c['court'] for c in cases).most_common(10))}; D.D.C. share {pct(sum(c['court']=='dcd' for c in cases),len(cases))}
- Search buckets: {dict(C(c['search_bucket'] for c in cases))}

## Labels (per ruling)
- Decisions vs Jev outcome agreement: **{pct(ag,len(both))}** → `model_agreed`: {sum(o['label_status']=='model_agreed' for o in rul)}, `needs_review`: {sum(o['label_status']=='needs_review' for o in rul)}
- Decisions vs heuristic: {pct(sum(o['decisions_outcome']==o['heuristic_outcome'] for o in hd),len(hd))}; Jev vs heuristic: {pct(sum(o['jev_outcome']==o['heuristic_outcome'] for o in hj),len(hj))}; heuristic fired on {pct(sum(1 for o in rul if o['heuristic_outcome']),len(rul))}; all three agree: {all3}
- Final outcome (model_agreed): {dict(C(o['outcome_final'] for o in rul if o['outcome_final']))}
- Decisions outcomes: {dict(C(o['decisions_outcome'] for o in rul))}; Jev: {dict(C(o['jev_outcome'] for o in rul))}
- Claim type (case-level): {dict(C(c['claim_type'] for c in cases))}
- Claim type Decisions vs Jev agreement: {pct(sum(o['decisions_claim_type']==o['jev_claim_type'] for o in rul if o['decisions_claim_type']),sum(1 for o in rul if o['decisions_claim_type']))}
- API errors: {dict(err)}

## RECAP (free, nothing purchased)
- Motion to dismiss / 12(b)(6) papers free on RECAP: **{pct(free,len(rv))}** of dockets (check errors: {len(cases)-len(rv)})

## Cost
- Decisions ≈ {tok['decisions']:,} input tokens ≈ ${cost['decisions']:.2f}; Jev ≈ {tok['jev']:,} ≈ ${cost['jev']:.2f}. CourtListener is free.

## Supabase
`005_load_batch2.sql` is idempotent, skips batch-1 cases/dockets, and widens the `label_status` CHECK to allow model_agreed/needs_review. **Not applied.**

## Next steps
1. Review the `needs_review` rulings (or exclude them), then apply 004, then 005.
2. Stage 2: predict from RECAP motion text where it's free; use redacted opinion background sections elsewhere.
"""
open("REPORT.md","w").write(md)
q=lambda v:"NULL" if v is None or v=="" else ("true" if v is True else "false" if v is False else str(v) if isinstance(v,int) else "'"+str(v).replace("'","''")+"'")
now=datetime.datetime.now().astimezone().isoformat(timespec="seconds")
L=["-- 005_load_batch2.sql: batch 2 employment 12(b)(6) rulings, against the post-003a litigation schema. PENDING, not applied.",
"-- Idempotent: ON CONFLICT DO NOTHING; cases whose docket_id already exists (batch 1) are skipped, along with their motions/rulings.",
"-- Works before or after 004. Apply 004 first if possible.","BEGIN;",
"-- label_status vocabulary for batch 2 (Rebecca: model agreement = final, no hand spot-check)",
"ALTER TABLE litigation.rulings DROP CONSTRAINT IF EXISTS rulings_label_status_check;",
"ALTER TABLE litigation.rulings ADD CONSTRAINT rulings_label_status_check CHECK (label_status IN ('review','auto_accepted','human_verified','excluded','model_agreed','needs_review'));",
f"INSERT INTO litigation.model_runs(run_id,tool,model,stage,started_at,notes) VALUES ('batch2-decisions','decisions','gpt-6-luna','outcome_label',{q(now)},'batch2 label2.py'),('batch2-jev','jev','jev-1.13.0','outcome_label',{q(now)},'batch2 label2.py') ON CONFLICT DO NOTHING;"]
for c in cases:
    L.append(f"INSERT INTO litigation.cases(case_id,case_name,court,docket_id,claim_type,class_vehicle,search_bucket) SELECT {q(c['id'])},{q(c['case_name'])},{q(c['court'])},{c['docket_id']},{q(c['claim_type'])},'unknown',{q(c['search_bucket'])} WHERE NOT EXISTS (SELECT 1 FROM litigation.cases WHERE docket_id={c['docket_id']} OR case_id={q(c['id'])});")
    for k,o in enumerate(c["rulings"]):
        mid=f"{c['id']}-m{k+1}";doc=None
        L.append(f"INSERT INTO litigation.motions(motion_id,case_id,motion_text_free) SELECT {q(mid)},{q(c['id'])},{q(bool(c['recap_mtd_free']))} WHERE EXISTS (SELECT 1 FROM litigation.cases WHERE case_id={q(c['id'])} AND docket_id={c['docket_id']}) ON CONFLICT DO NOTHING;")
        L.append(f"INSERT INTO litigation.rulings(ruling_id,motion_id,date_filed,opinion_url,dispositive_excerpt,decisions_outcome,jev_outcome,heuristic_outcome,decisions_claim_type,jev_claim_type,outcome_final,label_status,decisions_run_id,jev_run_id,labeled_at) SELECT {q(c['id']+'-r'+str(k+1))},{q(mid)},{q(o['date_filed'])},{q(o['url'])},{q(o['dispositive_excerpt'])},{q(o['decisions_outcome'])},{q(o['jev_outcome'])},{q(o['heuristic_outcome'])},{q(o['decisions_claim_type'])},{q(o['jev_claim_type'])},{q(o['outcome_final'])},{q(o['label_status'])},'batch2-decisions','batch2-jev',{q(now)} WHERE EXISTS (SELECT 1 FROM litigation.motions WHERE motion_id={q(mid)}) ON CONFLICT DO NOTHING;")
L+=["SELECT (SELECT count(*) FROM litigation.cases) cases,(SELECT count(*) FROM litigation.motions) motions,(SELECT count(*) FROM litigation.rulings) rulings;","COMMIT;"]
open("005_load_batch2.sql","w").write("\n".join(L)+"\n");print(md)
