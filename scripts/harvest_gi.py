import subprocess,json,os,re,time,html,urllib.request,urllib.error
K="DEMO_KEY";A="https://api.govinfo.gov"
def req(url,body=None,raw=False):
    for i in range(5):
        try:
            r=urllib.request.Request(url+("&" if "?" in url else "?")+"api_key="+K,data=json.dumps(body).encode() if body else None,headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(r,timeout=60) as f: d=f.read()
            time.sleep(1.5); return d.decode("utf-8","replace") if raw else json.loads(d)
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(30*(i+1)); continue
            if e.code==404: return None
            raise
B='collection:USCOURTS AND "motion to dismiss" AND "12(b)(6)" AND ("collective action" OR "putative class" OR "class action" OR "similarly situated") AND publishdate:range(2022-01-01,2026-10-01)'
T={"flsa":'"Fair Labor Standards Act"',"state_wage_hour":'("wage and hour" OR "New York Labor Law" OR "California Labor Code" OR "unpaid wages")',
"title_vii":'"Title VII"',"adea":'"Age Discrimination in Employment Act"',"ada":'"Americans with Disabilities Act" AND employer'}
PER={"flsa":8,"state_wage_hour":7,"title_vii":5,"adea":4,"ada":4}
b1={l.strip() for l in open("../../labels.json") for _ in [0]}  # placeholder
b1names={m["case_name"].lower() for m in json.load(open("../../labels.json"))}
pool={};counts={}
for t,q in T.items():
    d=req(A+"/search",{"query":f"{B} AND {q}","pageSize":40,"offsetMark":"*","sorts":[{"field":"relevancy","sortOrder":"DESC"}]})
    counts[t]=d["count"];n=0
    for r in d["results"]:
        pk=r["packageId"];court=pk.split("-")[1]
        if not re.fullmatch(r"[a-z]{2,4}d",court) or court in pool or pk in pool: continue  # district courts only
        if r["title"].lower() in b1names: continue
        pool[pk]={"package_id":pk,"granule_id":r["granuleId"],"case_name":r["title"],"court":court,"date_filed":r["dateIssued"],"search_bucket":t,"source":"govinfo"}
        n+=1
        if n>=PER[t]: break
    print(t,counts[t],n,flush=True)
idx=[]
for i,(pk,c) in enumerate(pool.items()):
    cid=f"g{i:02d}";fn=f"cases/{cid}.txt";g=c["granule_id"]
    if not os.path.exists(fn):
        r=urllib.request.Request(f"{A}/packages/{pk}/granules/{g}/pdf?api_key={K}")
        for k in range(4):
            try: open(f"cases/{cid}.pdf","wb").write(urllib.request.urlopen(r,timeout=90).read()); break
            except urllib.error.HTTPError as e:
                if e.code==429: time.sleep(30*(k+1))
                else: raise
        time.sleep(1.5); subprocess.run(["pdftotext","-layout",f"cases/{cid}.pdf",fn])
        sm=req(f"{A}/packages/{pk}/granules/{g}/summary") or {}; c["docket_text"]=sm.get("docketText")
    c.update(id=cid,source_url=f"https://www.govinfo.gov/app/details/{pk}/{g}",pdf_url=f"https://www.govinfo.gov/content/pkg/{pk}/pdf/{g}.pdf",chars=os.path.getsize(fn))
    idx.append(c)
json.dump({"counts":counts,"cases":idx},open("cases/index.json","w"),indent=1);print("DONE",len(idx))
