import json,re
from cl import get
meta=json.load(open("cases/index.json"));out=[]
MTD=re.compile(r"motion to dismiss|12\(b\)\(6\)|motion for judgment on the pleadings",re.I)
for m in meta:
    r={"id":m["id"],"docket_id":m["docket_id"]}
    try:
        d=get("recap-documents/",{"docket_entry__docket__id":m["docket_id"],"is_available":"true","fields":"id,description,document_number,is_available,filepath_local,page_count","page_size":100})
        docs=d["results"]
        hit=[x for x in docs if MTD.search(x.get("description") or "")]
        r.update(free_docs=d.get("count",len(docs)),mtd_free=bool(hit),mtd_docs=[{"id":x["id"],"desc":(x["description"] or "")[:120],"num":x.get("document_number")} for x in hit[:3]])
        if not hit and docs==[]:
            e=get("docket-entries/",{"docket":m["docket_id"],"fields":"entry_number,description","page_size":100})
            r["entries"]=e.get("count");r["mtd_entry_listed"]=any(MTD.search(x.get("description") or "") for x in e["results"])
    except Exception as ex: r["error"]=str(ex)[:200]
    out.append(r);print(r["id"],r.get("free_docs"),r.get("mtd_free"),r.get("error",""),flush=True)
json.dump(out,open("recap.json","w"),indent=1)
