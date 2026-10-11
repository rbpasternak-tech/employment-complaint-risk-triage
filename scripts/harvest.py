import json,os,re,html,collections,sys
from cl2 import get,N
S="state.json"; st=json.load(open(S)) if os.path.exists(S) else {}
def save(): json.dump(st,open(S+".tmp","w")); os.replace(S+".tmp",S)
if "courts" not in st:
    cs=[];u="courts/?jurisdiction=FD&fields=id&page_size=100"
    while u: d=get(u); cs+=[c["id"] for c in d["results"]]; u=d.get("next")
    st["courts"]=cs; save()
courts=set(st["courts"])
BASE='("12(b)(6)" OR "failure to state a claim") AND ("class action" OR "collective action" OR "putative class" OR "similarly situated")'
TYPES={"flsa":'(FLSA OR "Fair Labor Standards")',"state_wage_hour":'("Labor Code" OR NYLL OR "New York Labor Law" OR "wage and hour" OR "unpaid wages")',
 "title_vii":'"Title VII"',"ada":'"Americans with Disabilities Act" AND (employee OR employer OR employment)',"adea":'(ADEA OR "Age Discrimination in Employment")',
 "erisa":'ERISA AND (employee OR participants)',"warn":'("WARN Act" OR "Worker Adjustment and Retraining")'}
st.setdefault("pool",{});st.setdefault("counts",{});st.setdefault("next",{})
for t,q in TYPES.items():
    if st["next"].get(t)=="DONE": continue
    nxt=st["next"].get(t)
    if not nxt:
        d=get("search/",{"q":f"{BASE} AND {q}","type":"o","filed_after":"2018-01-01","filed_before":"2025-12-31","order_by":"score desc"})
        st["counts"][t]=d["count"]
    else: d=get(nxt)
    pages=st.setdefault("pages",{}).get(t,0)
    while True:
        for r in d["results"]:
            if r["court_id"] in courts and r.get("opinions"):
                st["pool"].setdefault(str(r["cluster_id"]),{"cluster_id":r["cluster_id"],"docket_id":r["docket_id"],"case_name":r["caseName"],"court":r["court_id"],
                  "date_filed":r["dateFiled"],"url":"https://www.courtlistener.com"+r["absolute_url"],"opinion_ids":[o["id"] for o in r["opinions"]],"buckets":[]})["buckets"].append(t)
        pages+=1; st["pages"][t]=pages
        if not d.get("next") or pages>=15: st["next"][t]="DONE"; save(); break
        st["next"][t]=d["next"]; save(); d=get(d["next"])
    print(t,st["counts"].get(t),"pool",len(st["pool"]),flush=True)
# select dockets
old={json.loads(l)["docket_id"] for l in []}
b1={m["docket_id"] for m in json.load(open("../cases/index.json"))}
if "selected" not in st:
    by=collections.defaultdict(list)
    for c in st["pool"].values():
        if c["docket_id"] in b1: continue
        by[c["docket_id"]].append(c)
    dockets=list(by.values())
    TARGET=260; cc=collections.Counter(); tc=collections.Counter(); sel=[]
    # round robin over types, prefer least-used courts
    q={t:[d for d in dockets if d[0]["buckets"][0]==t or t in d[0]["buckets"]] for t in TYPES}
    used=set()
    while len(sel)<TARGET:
        added=False
        for t in TYPES:
            cand=[d for d in q[t] if d[0]["docket_id"] not in used and cc[d[0]["court"]]<(52 if d[0]["court"]=="dcd" else 18)]
            if not cand: continue
            d=min(cand,key=lambda d:cc[d[0]["court"]])
            used.add(d[0]["docket_id"]);cc[d[0]["court"]]+=1;tc[t]+=1;sel.append({"bucket":t,"clusters":d});added=True
            if len(sel)>=TARGET: break
        if not added: break
    st["selected"]=sel; save(); print("selected",len(sel),dict(tc),flush=True)
# fetch opinions
idx=[]
for i,s in enumerate(st["selected"]):
    cid=f"b{i:03d}"; cl=sorted(s["clusters"],key=lambda c:c["date_filed"])[:3]; ops=[]
    for j,c in enumerate(cl):
        fn=f"cases/{cid}-{j}.txt"
        if not os.path.exists(fn):
            o=get(f"opinions/{c['opinion_ids'][0]}/",{"fields":"plain_text,html_with_citations,html,xml_harvard,html_lawbox,html_columbia"})
            tx=o.get("plain_text") or ""
            if len(tx)<500:
                h=next((o[k] for k in ["html_with_citations","html","xml_harvard","html_lawbox","html_columbia"] if o.get(k)),"")
                tx=html.unescape(re.sub(r"<[^>]+>"," ",h))
            open(fn,"w").write(tx)
        ops.append({"opinion_key":f"{cid}-{j}","cluster_id":c["cluster_id"],"opinion_id":c["opinion_ids"][0],"date_filed":c["date_filed"],"url":c["url"],"chars":os.path.getsize(fn)})
    c0=cl[0]; idx.append({"id":cid,"case_name":c0["case_name"],"court":c0["court"],"docket_id":c0["docket_id"],"search_bucket":s["bucket"],"opinions":ops})
    if i%10==0: print("fetched",i,"requests",N[0],flush=True)
json.dump(idx,open("cases/index.json","w"),indent=1); print("HARVEST DONE",len(idx),flush=True)
