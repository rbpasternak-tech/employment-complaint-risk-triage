import json,re,datetime,sys
sys.path.insert(0,"../framework"); from loaders import LEAK_MARKERS
M=json.load(open("cases/manifest_raw.json"))
SRC={"g00":"govinfo_docket_summary","g01":"govinfo_docket_summary","g02":"govinfo_docket_summary","g03":"govinfo_docket_summary","g04":"govinfo_docket_summary",
 "g06":"govinfo_docket_summary","g11":"govinfo_docket_summary","g12":"govinfo_docket_summary","g13":"govinfo_docket_summary","g14":"govinfo_docket_summary",
 "x2":"opinion_text","x3":"opinion_text","x4":"opinion_text(ECF 43 in folder)"}
TOOL={"e00":"denied","e03":"granted","e07":"granted_in_part","e08":"denied","e10":"denied","g05":None}
DATES={"x2":"2024-01-01","x3":"2024-06-01","x4":"2024-02-09"}  # approx ruling dates (year-level for x2/x3)
def fdate(t):
    m=re.search(r"Filed:?\s*(\d{2}/\d{2}/\d{2,4})",t[:600],re.I)
    if not m: return None
    s=m.group(1); return datetime.datetime.strptime(s,"%m/%d/%y" if len(s)==8 else "%m/%d/%Y").date().isoformat()
F=[];matters=[]
for c in M:
    k=c["id"];rd=(DATES.get(k) or c["date"] or "")[:10]
    of=c.get("outcome_final") or TOOL.get(k)
    docs=[]
    for d in c["docs"]:
        if "error" in d or d["attachment"]!="0": continue
        p=f"{k}/{d["file"][:-4]}.txt"
        try: t=open("cases/"+p,errors="replace").read()
        except FileNotFoundError: continue
        d["filed"]=fdate(t) or ("0000-00-00" if d["doc_number"]=="1" else None);d["path"]=p;d["text"]=t;docs.append(d)
    # doc 1 is the complaint on every docket; fix misclassifications
    for d in docs:
        if d["doc_number"]=="1" and d["type"] in("other","amended_complaint") and not LEAK_MARKERS.search(d["text"][:20000]): d["type"]="complaint"
    for d in docs:
        if d["type"]!="complaint" and (LEAK_MARKERS.search(d["text"][:3000]) or re.search(r"MINUTE ORDER|MEMORANDUM OPINION|^\s*ORDER\b",d["text"][:3000],re.M)): d["type"]="ruling_or_order"
    pre=[d for d in docs if d["filed"] and rd and d["filed"]<rd] if len(rd)==10 else docs
    comps=[d for d in pre if d["type"] in("complaint","amended_complaint") and not LEAK_MARKERS.search(d["text"][:20000]) and d["chars"]>3000]
    op=max(comps,key=lambda d:d["filed"] or "") if comps else None
    mot=[d for d in pre if d["type"]=="motion" and (not op or (d["filed"] or "")>=(op["filed"] or ""))]
    opp=[d for d in pre if d["type"]=="opposition" and (not op or (d["filed"] or "")>=(op["filed"] or ""))]
    rul=[d for d in docs if d["type"]=="ruling_or_order" and d["filed"] and rd and d["filed"][:7]==rd[:7]]
    if not op: print("skip",k,"no pre-ruling complaint"); continue
    mid=f"{k}"
    F.append({"filing_id":f"{k}-doc{op['doc_number']}","matter_id":mid,"filing_kind":"complaint" if op["type"]=="complaint" else "amended_complaint","path":op["path"],"source_url":op["source_url"],"filed":op["filed"]})
    for d in mot[-1:]: F.append({"filing_id":f"{k}-doc{d['doc_number']}","matter_id":mid,"filing_kind":"motion","path":d["path"],"source_url":d["source_url"],"filed":d["filed"]})
    for d in rul[:1]: F.append({"filing_id":f"{k}-doc{d['doc_number']}","matter_id":mid,"filing_kind":"ruling","path":d["path"],"source_url":d["source_url"],"filed":d["filed"]})
    matters.append({"matter_id":mid,"case_name":c["case_name"],"court":c["court"],"ruling_date":c["date"],"outcome_final":of,
      "outcome_source":SRC.get(k) or ("tool_agreement_UNCONFIRMED" if of else None),"claims_survived":None if not of else of in("denied","granted_in_part"),
      "complaint":op["filing_id"] if "filing_id" in op else f"{k}-doc{op['doc_number']}","complaint_filed":op["filed"],
      "motion_free":bool(mot),"opposition_free":bool(opp),"ruling_in_folder":bool(rul),"ia_item":c["ia_item"]})
json.dump([{k:v for k,v in f.items() if k in("filing_id","matter_id","filing_kind","path")}|{"source_url":f["source_url"],"filed":f["filed"]} for f in F],open("cases/filings.json","w"),indent=1)
json.dump(matters,open("cases/manifest.json","w"),indent=1)
for m in matters: print(m["matter_id"],m["outcome_final"],m["outcome_source"][:14] if m["outcome_source"] else None,m["complaint"],m["complaint_filed"],"mot",m["motion_free"],"opp",m["opposition_free"],"rul",m["ruling_in_folder"])
print(len(matters),"matters",len(F),"filings")
