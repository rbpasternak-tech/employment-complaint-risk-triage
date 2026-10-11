"""Phase 1: complaint-only risk scoring (Decisions, Jev, GPT baseline). Keys from env only; never printed."""
import json,os,re,sys,time,concurrent.futures as cf,urllib.request,urllib.error
sys.path.insert(0,"/workspace/litigation-classifier/framework")
import loaders
OA=os.environ["OPENAI_API_KEY"]; JV=os.environ["JEV_API_KEY"]
BASE_MODEL="gpt-6.1-sol"
CT={"flsa":"Fair Labor Standards Act claims (often collective actions).","state_wage_hour":"State wage-and-hour law, e.g. California Labor Code, NYLL.",
"title_vii":"Title VII employment discrimination.","ada":"Americans with Disabilities Act employment claims.","adea":"Age discrimination in employment.",
"erisa":"ERISA benefits/fiduciary claims.","warn":"WARN Act mass-layoff notice claims.","other":"Any other claim type, or not an employment case."}
FE=json.load(open("../framework/config.feature_extraction.json"))["schema"]; FE["claim_type"]["choices"]=CT
RS=json.load(open("../framework/config.risk_score.json"))["schema"]
RS["risk_tier"]["question"]="How likely is it that at least one claim in this complaint survives a Rule 12(b)(6) motion to dismiss?"
RS["risk_tier"]["choices"]={"high":"Very likely at least one claim survives (well-pled facts, recognized theory)","medium":"Uncertain; some claims look vulnerable","low":"Likely dismissed in full (conclusory or legally defective)"}
EXTRA_PRED={"arbitration_mentioned":"Does the complaint mention an arbitration agreement, arbitration clause or class-action waiver?",
            "multiple_claim_types":"Does the complaint assert claims under more than one statute (e.g. FLSA plus state wage law, or Title VII plus state law)?"}
def post(url,key,body,timeout=120):
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    t=time.perf_counter()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r),None,(time.perf_counter()-t)*1000
        except urllib.error.HTTPError as e: err=f"HTTP {e.code}: {e.read().decode()[:300]}"
        except Exception as e: err=repr(e)[:300]
        time.sleep(3*(attempt+1))
    return None,err,(time.perf_counter()-t)*1000
def dec_q(schema,preds):
    qs=[]
    for n,s in schema.items():
        if s["type"]=="choice": qs.append({"type":"choice","name":n,"instructions":s["question"],"choices":[{"value":k,"description":v} for k,v in s["choices"].items()]})
        else: qs.append({"type":"predicate","name":n,"instructions":s["question"]})
    qs+=[{"type":"predicate","name":n,"instructions":q} for n,q in preds.items()]; return qs
def jev_q(schema,preds):
    qs={}
    for n,s in schema.items():
        qs[n]={"type":"choice","instructions":s["question"],"criteria":s["choices"]} if s["type"]=="choice" else {"type":"noul","instructions":s["question"]}
    qs.update({n:{"type":"noul","instructions":q} for n,q in preds.items()}); return qs
def run_dec(x,schema,preds):
    o,e,ms=post("https://api.openai.com/v1/decisions",OA,{"model":"gpt-6-luna","input":x,"questions":dec_q(schema,preds)})
    if e: return {"error":e,"ms":ms}
    a={q.get("name"):q for q in o.get("answers",[])};u=o.get("usage") or {}
    r={n:(a.get(n,{}).get("choice") if a.get(n,{}).get("choice") is not None else a.get(n,{}).get("probability")) for n in list(schema)+list(preds)}
    tok=u.get("input_tokens") or u.get("prompt_tokens"); r.update(tok=tok or len(x)//4,tok_est=tok is None,ms=ms); return r
def run_jev(x,schema,preds):
    o,e,ms=post("https://api.typesafe.ai/v1/systemone",JV,{"model":"jev-1.13.0","state":x,"questions":jev_q(schema,preds)})
    if e: return {"error":e,"ms":ms}
    a=o.get("answers",{});u=o.get("usage") or {}
    r={n:(a.get(n,{}).get("choice") if "choice" in a.get(n,{}) else a.get(n,{}).get("noul")) for n in list(schema)+list(preds)}
    tok=u.get("input_tokens"); r.update(tok=tok or len(x)//4,tok_est=tok is None,ms=ms); return r
BASE_PROMPT="""You are an experienced employment-defense litigator triaging an inbound complaint. You see ONLY the complaint (no motion, no ruling, no docket).
Predict whether AT LEAST ONE claim will survive a Rule 12(b)(6) motion to dismiss (i.e. the motion is denied or granted only in part).
Consider: class/collective vehicle, claim types, factual specificity (hours, pay rates, dates, comparators vs. conclusory boilerplate), circuit pleading standards
(e.g. Second Circuit Lundy/Dejesus for FLSA overtime), joint-employer theories, arbitration/waiver issues, plaintiff counsel sophistication.
Return JSON: risk_tier (high = likely at least one claim survives; medium = uncertain; low = likely dismissed in full), p_survive (0-1), rationale (<=60 words), signals (list of short strings)."""
SCH={"type":"object","additionalProperties":False,"required":["risk_tier","p_survive","rationale","signals"],"properties":{
 "risk_tier":{"type":"string","enum":["high","medium","low"]},"p_survive":{"type":"number"},"rationale":{"type":"string"},"signals":{"type":"array","items":{"type":"string"}}}}
def run_base(x):
    body={"model":BASE_MODEL,"reasoning":{"effort":"medium"},"input":[{"role":"system","content":BASE_PROMPT},{"role":"user","content":"COMPLAINT:\n"+x}],
          "text":{"format":{"type":"json_schema","name":"risk","schema":SCH,"strict":True}}}
    o,e,ms=post("https://api.openai.com/v1/responses",OA,body,timeout=300)
    if e: return {"error":e,"ms":ms}
    txt="".join(c.get("text","") for it in o.get("output",[]) if it.get("type")=="message" for c in it.get("content",[]))
    try: r=json.loads(txt)
    except Exception: return {"error":"bad json: "+txt[:200],"ms":ms}
    u=o.get("usage") or {}; r.update(model=o.get("model"),tok_in=u.get("input_tokens"),tok_out=u.get("output_tokens"),tok_reason=(u.get("output_tokens_details") or {}).get("reasoning_tokens"),ms=ms); return r
FIRM=re.compile(r"^[^\n]{0,80}\b(LLP|L\.L\.P\.|PLLC|P\.L\.L\.C\.|P\.C\.|LLC|Law (Firm|Group|Office|Offices)|Associates|& [A-Z][a-z]+)\b[^\n]{0,40}$",re.M)
def firm(t):
    tail=t[-6000:]; ms=[m.group(0).strip() for m in FIRM.finditer(tail)]
    ms=[m for m in ms if not re.search(r"defendant|v\.|inc\.|employer",m,re.I)]
    return ms[-1][:120] if ms else None
def trim(t):
    # strip any 'ordered' language just in case; complaints carry facts up front, prayer + signature at the end
    return t if len(t)<=60000 else t[:52000]+"\n\n[...]\n\n"+t[-8000:]
man={m["matter_id"]:m for m in json.load(open("cases/manifest.json"))}
def one(d):
    full=open(os.path.join("cases",[f for f in json.load(open("cases/filings.json")) if f["filing_id"]==d["motion_id"]][0]["path"])).read()
    x=trim(full); assert not loaders.LEAK_MARKERS.search(x[:20000])
    r={"matter_id":d["doc_id"],"filing_id":d["motion_id"],"chars_sent":len(x),"plaintiff_firm_regex":firm(full),
       "arbitration_regex":bool(re.search(r"arbitrat",full,re.I))}
    with cf.ThreadPoolExecutor(5) as ex:
        f1=ex.submit(run_dec,x,FE,{"arbitration_mentioned":EXTRA_PRED["arbitration_mentioned"]}); f2=ex.submit(run_jev,x,FE,{"arbitration_mentioned":EXTRA_PRED["arbitration_mentioned"]})
        f3=ex.submit(run_dec,x,RS,{}); f4=ex.submit(run_jev,x,RS,{}); f5=ex.submit(run_base,x)
        r.update(features={"decisions":f1.result(),"jev":f2.result()},risk={"decisions":f3.result(),"jev":f4.result(),"baseline":f5.result()})
    print(r["matter_id"],{k:(v.get("risk_tier"),v.get("p_survive"),v.get("error","")[:60]) for k,v in r["risk"].items()},flush=True); return r
docs=list(loaders.complaints("cases/filings.json","cases"))
with cf.ThreadPoolExecutor(4) as ex: res=list(ex.map(one,docs))
json.dump(res,open("risk_raw.json","w"),indent=1)
