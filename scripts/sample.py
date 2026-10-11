import json,re,collections,html
from cl import get
courts=[];u="courts/?jurisdiction=FD&fields=id&page_size=100"
while u:
    d=get(u); courts+= [c["id"] for c in d["results"]]; u=d.get("next")
print(len(courts),"district courts",flush=True)
BASE='("12(b)(6)" OR "failure to state a claim" OR "motion to dismiss") AND ("class action" OR "collective action" OR "putative class" OR "class members" OR "similarly situated")'
TYPES={"FLSA":'(FLSA OR "Fair Labor Standards")',"state_wage_hour":'("Labor Code" OR NYLL OR "New York Labor Law" OR "wage and hour" OR "unpaid wages")',
 "Title VII":'"Title VII"',"ADA":'"Americans with Disabilities Act" AND employ*',"ADEA":'(ADEA OR "Age Discrimination in Employment")',
 "ERISA":'ERISA',"WARN":'("WARN Act" OR "Worker Adjustment and Retraining")'}
counts={};pools={}
for t,q in TYPES.items():
    p={"q":f"{BASE} AND {q}","type":"o","filed_after":"2023-01-01","filed_before":"2025-12-31","order_by":"score desc"}
    d=get("search/",p);counts[t]=d["count"];rs=d["results"]
    for _ in range(3):
        if not d.get("next"): break
        d=get(d["next"]); rs+=d["results"]
    rs=[r for r in rs if r["court_id"] in courts]
    pools[t]=rs;print(t,d["count"],flush=True)
json.dump({"query_base":BASE,"types":TYPES,"counts":counts},open("search_counts.json","w"),indent=1)
pick=[];seen=set();cc=collections.Counter();per={"FLSA":9,"state_wage_hour":8,"Title VII":7,"ADA":6,"ADEA":6,"ERISA":8,"WARN":6}
for t,rs in pools.items():
    n=0
    for r in rs:
        c=r["court_id"]
        if r["cluster_id"] in seen or cc[c]>=(12 if c=="dcd" else 4) or not r.get("opinions"): continue
        pick.append((t,r));seen.add(r["cluster_id"]);cc[c]+=1;n+=1
        if n>=per[t]: break
meta=[]
for i,(t,r) in enumerate(pick):
    oid=r["opinions"][0]["id"]; o=get(f"opinions/{oid}/",{"fields":"plain_text,html_with_citations,html,xml_harvard,html_lawbox,html_columbia"})
    tx=o.get("plain_text") or ""
    if len(tx)<500:
        h=next((o[k] for k in ["html_with_citations","html","xml_harvard","html_lawbox","html_columbia"] if o.get(k)),"")
        tx=html.unescape(re.sub(r"<[^>]+>"," ",h))
    cid=f"e{i:02d}"; open(f"cases/{cid}.txt","w").write(tx)
    m={"id":cid,"search_bucket":t,"case_name":r["caseName"],"court":r["court_id"],"date_filed":r["dateFiled"],
       "url":"https://www.courtlistener.com"+r["absolute_url"],"docket_id":r["docket_id"],"cluster_id":r["cluster_id"],"opinion_id":oid,"chars":len(tx)}
    meta.append(m);print(cid,t,m["court"],len(tx),m["case_name"][:50],flush=True)
json.dump(meta,open("cases/index.json","w"),indent=1)
