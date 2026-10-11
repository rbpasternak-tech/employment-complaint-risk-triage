import json,statistics as st
raw=json.load(open("risk_raw.json")); man={m["matter_id"]:m for m in json.load(open("cases/manifest.json"))}
PRICE={"decisions":(0.10,0),"jev":(0.042,0),"baseline":(2.0,10.0)}
TOOLS=["decisions","jev","baseline"]
def cost(t,r):
    if t=="baseline": return ((r.get("tok_in") or 0)*2.0+(r.get("tok_out") or 0)*10.0)/1e6
    return (r.get("tok") or 0)*PRICE[t][0]/1e6
rows=[]
for r in raw:
    m=man.get(r["matter_id"],{}); o=m.get("outcome_final"); src=m.get("outcome_source")
    row={"matter_id":r["matter_id"],"filing_id":r["filing_id"],"case_name":m.get("case_name"),"court":m.get("court"),"outcome_final":o,
         "outcome_source":src,"confirmed":bool(src) and "UNCONFIRMED" not in src,"survived":(o in("denied","granted_in_part")) if o else None,
         "chars_sent":r["chars_sent"],"plaintiff_firm":r["plaintiff_firm_regex"],"arbitration_regex":r["arbitration_regex"],"features":{},"risk":{}}
    for t in ("decisions","jev"):
        f=r["features"][t]; row["features"][t]={k:f.get(k) for k in ["class_vehicle","claim_type","factual_specificity","plaintiff_count_bucket","damages_pled","arbitration_mentioned"]}
        row["features"][t].update(cost_usd=cost(t,f),latency_ms=round(f.get("ms",0)))
    for t in TOOLS:
        x=r["risk"][t]; d={"risk_tier":x.get("risk_tier"),"p_survive":x.get("p_survive"),"cost_usd":cost(t,x),"latency_ms":round(x.get("ms",0))}
        if t=="baseline": d.update(rationale=x.get("rationale"),signals=x.get("signals"),model=x.get("model"))
        row["risk"][t]=d
    rows.append(row)
def metrics(sub):
    out={}
    for t in TOOLS:
        n=len(sub); hi=[r["risk"][t]["risk_tier"]=="high" for r in sub]; y=[r["survived"] for r in sub]
        cm={"high&survived":sum(h and s for h,s in zip(hi,y)),"high&dismissed":sum(h and not s for h,s in zip(hi,y)),
            "not_high&survived":sum((not h) and s for h,s in zip(hi,y)),"not_high&dismissed":sum((not h) and not s for h,s in zip(hi,y))}
        ps=[(r["risk"][t]["p_survive"],s) for r,s in zip(sub,y) if r["risk"][t]["p_survive"] is not None]
        out[t]={"n":n,"acc_high_vs_not":(cm["high&survived"]+cm["not_high&dismissed"])/n,"confusion":cm,
                "tiers":{k:sum(r["risk"][t]["risk_tier"]==k for r in sub) for k in("high","medium","low")},
                "brier":sum((p-s)**2 for p,s in ps)/len(ps),"brier_n":len(ps),"mean_p":sum(p for p,_ in ps)/len(ps)}
    out["base_rate_survived"]=sum(r["survived"] for r in sub)/len(sub)
    out["always_survive_brier"]=sum((out["base_rate_survived"]-r["survived"])**2 for r in sub)/len(sub)
    return out
conf=[r for r in rows if r["confirmed"]]; known=[r for r in rows if r["survived"] is not None]
summ={"confirmed_13":metrics(conf),"all_known_18":metrics(known)}
ops={}
for t in TOOLS:
    c=sum(r["risk"][t]["cost_usd"] for r in rows)+sum(r["features"].get(t,{}).get("cost_usd",0) for r in rows)
    ops[t]={"total_cost_usd_19":c,"usd_per_1k_complaints":c/len(rows)*1000,"median_latency_ms_risk":st.median(r["risk"][t]["latency_ms"] for r in rows),
            "model":{"decisions":"gpt-6-luna","jev":"jev-1.13.0","baseline":rows[0]["risk"]["baseline"]["model"]}[t]}
summ["ops"]=ops
summ["disagreements"]=[{"matter_id":r["matter_id"],**{t:(r["risk"][t]["risk_tier"],r["risk"][t]["p_survive"]) for t in TOOLS}} for r in rows if len({r["risk"][t]["risk_tier"] for t in TOOLS})>1]
fd=[]
for r in rows:
    diff={k:(r["features"]["decisions"][k],r["features"]["jev"][k]) for k in ["class_vehicle","claim_type","factual_specificity","plaintiff_count_bucket","damages_pled"] if r["features"]["decisions"][k]!=r["features"]["jev"][k]}
    if diff: fd.append({"matter_id":r["matter_id"],**diff})
summ["feature_disagreements"]=fd
json.dump({"run":"2026-10-11-phase1","definition":"survived = outcome_final in (denied, granted_in_part)","summary":summ,"cases":rows},open("risk_results.json","w"),indent=1)
print(json.dumps(summ,indent=1))
for r in rows: print(r["matter_id"],r["outcome_final"],r["confirmed"],r["plaintiff_firm"],r["features"]["decisions"],"|",r["risk"]["baseline"]["rationale"])
