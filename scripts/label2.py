import json,os,sys,concurrent.futures as cf
os.chdir(os.path.dirname(os.path.abspath(__file__)))
src=open("../label.py").read().split("meta=json.load")[0]; exec(src)
idx=json.load(open("cases/index.json"))
R=json.load(open("raw_labels.json")) if os.path.exists("raw_labels.json") else {}
def one(op):
    t=open(f"cases/{op['opinion_key']}.txt").read(); x=excerpt(t); h,s=heur(t)
    r={"heuristic":h,"dispositive_excerpt":s}
    if len(t)<300: r.update(decisions={"error":"no text"},jev={"error":"no text"}); return op["opinion_key"],r
    r["decisions"]=dec(x); r["jev"]=jev(x); return op["opinion_key"],r
todo=[o for c in idx for o in c["opinions"] if o["opinion_key"] not in R or "error" in R[o["opinion_key"]].get("decisions",{}) or "error" in R[o["opinion_key"]].get("jev",{})]
print("to label",len(todo),flush=True)
with cf.ThreadPoolExecutor(4) as ex:
    for i,(k,r) in enumerate(ex.map(one,todo)):
        R[k]=r
        if i%20==0: json.dump(R,open("raw_labels.json","w")); print("labeled",i,flush=True)
json.dump(R,open("raw_labels.json","w"),indent=1); print("LABEL DONE")
