import json,re,sys,concurrent.futures as cf
sys.path.insert(0,"/workspace/decisions-vs-jev")
from run import post,OA,JV,PRICE
OUT={"granted":"The court granted the Rule 12(b)(6) motion to dismiss in full (all challenged claims dismissed, with or without leave to amend).",
"denied":"The court denied the Rule 12(b)(6) motion to dismiss in full; the claims survive.",
"granted_in_part":"The court granted the 12(b)(6) motion in part and denied it in part (some claims survive).",
"not_reached":"The court did not rule on a 12(b)(6) motion on the merits (moot, not reached, decided on other grounds such as 12(b)(1), arbitration, transfer, or this is not a ruling on a motion to dismiss)."}
CT={"flsa":"Fair Labor Standards Act claims (often collective actions).","state_wage_hour":"State wage-and-hour law, e.g. California Labor Code, NYLL.",
"title_vii":"Title VII employment discrimination.","ada":"Americans with Disabilities Act employment claims.","adea":"Age discrimination in employment.",
"erisa":"ERISA benefits/fiduciary claims.","warn":"WARN Act mass-layoff notice claims.","other":"Any other claim type, or not an employment case."}
QO="What was the outcome of the Rule 12(b)(6) motion to dismiss decided in this opinion?"
QC="What is the primary type of employment claim asserted in this putative class or collective action?"
def excerpt(t):
    tail=t[-24000:]; head=t[:-24000]
    paras=[p for p in re.split(r"\n\s*\n|(?<=\.)\s{2,}",head) if "12(b)(6)" in p]
    ex="\n\n".join(paras)[:30000]+"\n\n[...]\n\n"+tail if paras else (t[:6000]+"\n\n[...]\n\n"+tail if head else t)
    return ex[:60000]
def dec(x):
    qs=[{"type":"choice","name":"out","instructions":QO,"choices":[{"value":k,"description":v} for k,v in OUT.items()]},
        {"type":"choice","name":"ct","instructions":QC,"choices":[{"value":k,"description":v} for k,v in CT.items()]}]
    o,e,ms=post("https://api.openai.com/v1/decisions",OA,{"model":"gpt-6-luna","input":x,"questions":qs})
    if e: return {"error":e}
    a={q.get("name"):q for q in o.get("answers",[])};u=o.get("usage") or {}
    return {"out":a.get("out",{}).get("choice"),"ct":a.get("ct",{}).get("choice"),"tok":u.get("input_tokens") or u.get("prompt_tokens") or len(x)//4,"ms":ms}
def jev(x):
    qs={"out":{"type":"choice","instructions":QO,"criteria":OUT},"ct":{"type":"choice","instructions":QC,"criteria":CT}}
    o,e,ms=post("https://api.typesafe.ai/v1/systemone",JV,{"model":"jev-1.13.0","state":x,"questions":qs})
    if e: return {"error":e}
    a=o.get("answers",{});u=o.get("usage") or {}
    return {"out":a.get("out",{}).get("choice"),"ct":a.get("ct",{}).get("choice"),"tok":u.get("input_tokens") or len(x)//4,"ms":ms}
DISP=re.compile(r"[^.\n]{0,200}\b(motions?\s+to\s+dismiss|motion)\b[^.]{0,200}?\b(is|are|be|hereby)\s+(hereby\s+)?(GRANTED\s+IN\s+PART|GRANTED|DENIED|granted\s+in\s+part|granted|denied)[^.]{0,200}\.?",re.I)
def heur(t):
    ms=list(DISP.finditer(t[-15000:]))
    if not ms: return None,""
    s=" ".join(m.group(0) for m in ms[-3:]); l=s.lower()
    if "in part" in l or ("granted" in l and "denied" in l): lab="granted_in_part"
    elif "moot" in l: lab="not_reached"
    elif "granted" in l: lab="granted"
    elif "denied" in l: lab="denied"
    else: lab=None
    return lab,re.sub(r"\s+"," ",ms[-1].group(0)).strip()[:400]
meta=json.load(open("cases/index.json"))
def one(m):
    t=open(f"cases/{m['id']}.txt").read(); x=excerpt(t)
    h,s=heur(t); r=dict(m,heuristic=h,dispositive_excerpt=s,excerpt_chars=len(x))
    if len(t)<300: r.update(decisions={"error":"no text"},jev={"error":"no text"}); return r
    r["decisions"]=dec(x); r["jev"]=jev(x); return r
with cf.ThreadPoolExecutor(4) as ex: res=list(ex.map(one,meta))
json.dump(res,open("raw_labels.json","w"),indent=1)
for r in res: print(r["id"],r["heuristic"],r["decisions"].get("out") or r["decisions"].get("error","")[:80],r["jev"].get("out") or r["jev"].get("error","")[:80])
