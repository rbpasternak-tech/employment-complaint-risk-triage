"""Config-driven Decisions vs Jev runner. Usage: python3 run.py [config.json] [--limit N] [--dry-run]
Same prompt + label schema to both tools. Keys come from env (same vars label.py/run.py use); never printed.
Writes JSONL rows shaped like litigation.predictions (post-003a), plus a model_runs header and a SQL loader."""
import json, os, sys, time, datetime, importlib, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, "/workspace/decisions-vs-jev")
OUTCOMES = ["granted", "denied", "granted_in_part", "not_reached"]
NORM = {"partial": "granted_in_part", "not_decided_on_12b6": "not_reached"}

def post(url, key, body):
    import urllib.request, urllib.error
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=90) as r: return json.load(r), None, (time.perf_counter() - t) * 1000
    except urllib.error.HTTPError as e: return None, f"HTTP {e.code}: {e.read().decode()[:300]}", (time.perf_counter() - t) * 1000
    except Exception as e: return None, type(e).__name__ + ": " + str(e)[:300], (time.perf_counter() - t) * 1000

def resolve_choices(v):
    """'@label.OUT' -> pull the dict from label.py without running it (label.py executes on import)."""
    if isinstance(v, dict): return v
    import ast; mod, name = v[1:].split(".")
    tree = ast.parse(open(os.path.join(ROOT, mod + ".py")).read())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == name for t in n.targets): return ast.literal_eval(n.value)
    raise KeyError(v)

def build_decisions(schema, text, model):
    qs = []
    for name, q in schema.items():
        if q["type"] == "choice": qs.append({"type": "choice", "name": name, "instructions": q["question"], "choices": [{"value": k, "description": d} for k, d in q["choices"].items()]})
        else: qs.append({"type": "predicate", "name": name, "instructions": q["question"]})
    return {"model": model, "input": text, "questions": qs}

def parse_decisions(o):
    a = {x.get("name"): x for x in o.get("answers", [])}; u = o.get("usage") or {}
    return {k: (v.get("choice") if "choice" in v else v.get("probability")) for k, v in a.items()}, u.get("input_tokens") or u.get("prompt_tokens")

def build_jev(schema, text, model):
    qs = {}
    for name, q in schema.items():
        qs[name] = {"type": "choice", "instructions": q["question"], "criteria": q["choices"]} if q["type"] == "choice" else {"type": "noul", "instructions": q["question"]}
    return {"model": model, "state": text, "questions": qs}

def parse_jev(o):
    a = o.get("answers", {}); u = o.get("usage") or {}
    return {k: (v.get("choice") if "choice" in v else v.get("noul")) for k, v in a.items()}, u.get("input_tokens")

ADAPTERS = {"decisions": (build_decisions, parse_decisions), "jev": (build_jev, parse_jev)}

def call(tool, tc, schema, doc, key, dry):
    build, parse = ADAPTERS[tool]; body = build(schema, doc["text"], tc["model"])
    if dry: ans, tok, err, ms = {}, None, "dry_run", 0.0
    else:
        o, err, ms = post(tc["url"], key, body)
        ans, tok = parse(o) if o else ({}, None)
    est = tok is None; tok = tok or len(json.dumps(body)) // 4
    out = ans.get("outcome"); out = NORM.get(out, out)
    p = ans.get("p_survive")
    return {"motion_id": doc["motion_id"], "run_id": None, "p_survive": round(float(p), 4) if isinstance(p, (int, float)) else None,
            "predicted_outcome": out if out in OUTCOMES else None,
            "features": {"tool": tool, "claim_type": ans.get("claim_type"), "doc_id": doc["doc_id"], "input_tokens": tok,
                         "tokens_estimated": est, "error": err, "extra_answers": {k: v for k, v in ans.items() if k not in ("outcome", "claim_type", "p_survive")}},
            "cost_usd": round(tok * tc["usd_per_m_input"] / 1e6, 8), "latency_ms": int(ms)}

def sql_lit(v):
    if v is None: return "NULL"
    if isinstance(v, (dict, list)): v = json.dumps(v)
    if isinstance(v, (int, float)): return str(v)
    return "'" + str(v).replace("'", "''") + "'"

def _feat_sql(r):
    a = r["features"]["extra_answers"]; a = dict(a, claim_type=r["features"]["claim_type"])
    cols = ["class_vehicle", "claim_type", "factual_specificity", "plaintiff_firm", "plaintiff_count_bucket", "damages_pled"]
    extra = {k: v for k, v in a.items() if k not in cols}
    vals = [r["motion_id"], r["run_id"]] + [a.get(c) for c in cols] + [extra, r["cost_usd"], r["latency_ms"]]
    return ("INSERT INTO triage.features(filing_id,run_id," + ",".join(cols) + ",extra,cost_usd,latency_ms) VALUES ("
            + ",".join(sql_lit(v) for v in vals) + ") ON CONFLICT (filing_id,run_id) DO NOTHING;\n")

def _risk_sql(r):
    a = r["features"]["extra_answers"]; p = r["p_survive"]
    tier = a.get("risk_tier") or (None if p is None else "high" if p >= 0.6 else "medium" if p >= 0.35 else "low")
    vals = [r["motion_id"], r["run_id"], p, tier, r["cost_usd"], r["latency_ms"]]
    return ("INSERT INTO triage.risk_scores(filing_id,run_id,p_survive,risk_tier,cost_usd,latency_ms) VALUES ("
            + ",".join(sql_lit(v) for v in vals) + ") ON CONFLICT (filing_id,run_id) DO NOTHING;\n")

TRIAGE_SQL = {"feature_extraction": _feat_sql, "risk_score": _risk_sql}

def main():
    args = sys.argv[1:]; cfgp = next((a for a in args if a.endswith(".json")), os.path.join(HERE, "config.json"))
    cfg = json.load(open(cfgp)); dry = "--dry-run" in args
    if "--limit" in args: cfg["limit"] = int(args[args.index("--limit") + 1])
    os.chdir(os.path.dirname(os.path.abspath(cfgp)))
    schema = {k: dict(v, choices=resolve_choices(v["choices"])) if v["type"] == "choice" else v for k, v in cfg["schema"].items()}
    run_date = cfg.get("run_date") or datetime.date.today().isoformat()
    docs = list(importlib.import_module("loaders").LOADERS[cfg["loader"]](**cfg.get("loader_args", {})))[: cfg.get("limit") or None]
    keys = {}
    for t, tc in cfg["tools"].items():
        keys[t] = os.environ.get(tc["key_env"])
        if not keys[t] and not dry: sys.exit(f"missing env var {tc['key_env']} (value never printed)")
    runs = {t: {"run_id": f"{run_date}-{cfg['dataset']}-{t}", "tool": t, "model": tc["model"], "stage": cfg["stage"],
                "started_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "notes": f"framework/run.py {os.path.basename(cfgp)}"} for t, tc in cfg["tools"].items()}
    jobs = [(t, d) for d in docs for t in cfg["tools"]]
    with cf.ThreadPoolExecutor(cfg.get("concurrency", 4)) as ex:
        rows = list(ex.map(lambda j: call(j[0], cfg["tools"][j[0]], schema, j[1], keys[j[0]], dry), jobs))
    for r in rows: r["run_id"] = runs[r["features"]["tool"]]["run_id"]
    outp = cfg["output"].format(dataset=cfg["dataset"], run_date=run_date); os.makedirs(os.path.dirname(outp) or ".", exist_ok=True)
    with open(outp, "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    cols = ["motion_id", "run_id", "p_survive", "predicted_outcome", "features", "cost_usd", "latency_ms"]
    with open(outp.replace(".jsonl", ".sql"), "w") as f:
        f.write("-- Generated by framework/run.py. Review, then run in Supabase. Idempotent.\nBEGIN;\n")
        for r in runs.values():
            f.write("INSERT INTO litigation.model_runs(run_id,tool,model,stage,started_at,notes) VALUES (" + ",".join(sql_lit(r[k]) for k in ["run_id", "tool", "model", "stage", "started_at", "notes"]) + ") ON CONFLICT DO NOTHING;\n")
        for r in rows:
            if r["features"]["error"]: continue
            if cfg["stage"] in TRIAGE_SQL:
                f.write(TRIAGE_SQL[cfg["stage"]](r)); continue
            f.write(f"INSERT INTO litigation.predictions({','.join(cols)}) VALUES (" + ",".join(sql_lit(r[c]) for c in cols) + ") ON CONFLICT (motion_id,run_id) DO NOTHING;\n")
        f.write("COMMIT;\n")
    for t in cfg["tools"]:
        rs = [r for r in rows if r["features"]["tool"] == t]; ok = [r for r in rs if not r["features"]["error"]]
        lat = sorted(r["latency_ms"] for r in ok); cost = sum(r["cost_usd"] for r in ok)
        print(f"{t}: {len(ok)}/{len(rs)} ok, median {lat[len(lat)//2] if lat else '-'} ms, ${cost:.4f}, ${1000*cost/len(ok) if ok else 0:.2f}/1k docs")
    print("wrote", outp, "and", outp.replace(".jsonl", ".sql"))

if __name__ == "__main__": main()
