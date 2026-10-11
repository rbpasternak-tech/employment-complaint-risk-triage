import json,os,concurrent.futures as cf
os.chdir(os.path.dirname(os.path.abspath(__file__)))
exec(open("../../label.py").read().split("meta=json.load")[0])
idx=json.load(open("cases/index.json"))["cases"]
R=json.load(open("raw_labels.json")) if os.path.exists("raw_labels.json") else {}
def one(c):
    t=open(f"cases/{c['id']}.txt").read();x=excerpt(t);h,s=heur(t);r={"heuristic":h,"dispositive_excerpt":s}
    if len(t)<300: r.update(decisions={"error":"no text"},jev={"error":"no text"})
    else: r["decisions"]=dec(x);r["jev"]=jev(x)
    return c["id"],r
todo=[c for c in idx if c["id"] not in R or "error" in R[c["id"]]["decisions"] or "error" in R[c["id"]]["jev"]]
with cf.ThreadPoolExecutor(4) as ex:
    for k,r in ex.map(one,todo): R[k]=r
json.dump(R,open("raw_labels.json","w"),indent=1)
for k,r in sorted(R.items()): print(k,r["heuristic"],r["decisions"].get("out") or r["decisions"].get("error","")[:60],r["jev"].get("out") or r["jev"].get("error","")[:60],r["decisions"].get("ct"),r["jev"].get("ct"))
