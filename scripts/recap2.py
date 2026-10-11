import json,re,os
from cl2 import get
idx=json.load(open("cases/index.json"));F="recap.json"
out=json.load(open(F)) if os.path.exists(F) else {}
MTD=re.compile(r"motion to dismiss|12\(b\)\(6\)|motion for judgment on the pleadings",re.I)
for m in idx:
    k=str(m["docket_id"])
    if k in out and "error" not in out[k]: continue
    r={}
    try:
        d=get("recap-documents/",{"docket_entry__docket__id":m["docket_id"],"is_available":"true","fields":"id,description,document_number","page_size":100})
        hit=[x for x in d["results"] if MTD.search(x.get("description") or "")]
        r.update(free_docs=d.get("count") or len(d["results"]),mtd_free=bool(hit),mtd_docs=[{"id":x["id"],"desc":(x.get("description") or "")[:120],"num":x.get("document_number")} for x in hit[:3]])
    except Exception as ex: r["error"]=str(ex)[:200]
    out[k]=r; json.dump(out,open(F,"w"),indent=1)
print("RECAP DONE",len(out))
