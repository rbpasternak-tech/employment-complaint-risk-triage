"""Rebuild dashboard/index.html from local data: labels.json (+ raw_labels.json for tokens/latency)
and batch2/labels.json, batch2/gi/labels.json if present. Usage: python3 build_dashboard.py"""
import json, os, glob, datetime, html
H = os.path.dirname(os.path.abspath(__file__)); P = {"decisions": 0.10, "jev": 0.042}
N = lambda v: None if v is None else {"not_decided_on_12b6": "not_reached", "partial": "granted_in_part"}.get(v, v.lower().replace(" ", "_").replace("-", "_"))
def load(p):
    try: return json.load(open(p))
    except Exception: return None
rows, usage, sources = [], [], []
b1 = load(f"{H}/labels.json") or []
for r in b1:
    rows.append({"batch": "batch1", "id": r["id"], "case": r["case_name"], "court": r["court"], "date": r.get("date_filed"),
        "claim": N(r.get("decisions_claim_type") if r.get("decisions_claim_type") == r.get("jev_claim_type") else r.get("decisions_claim_type")),
        "dct": N(r.get("decisions_claim_type")), "jct": N(r.get("jev_claim_type")),
        "d": N(r.get("decisions_outcome")), "j": N(r.get("jev_outcome")), "final": N(r.get("outcome_final")), "status": r.get("label_status"), "url": r.get("url"), "docket": r.get("docket_id")})
sources.append(f"labels.json ({len(b1)})")
for r in load(f"{H}/raw_labels.json") or []:
    for t in P:
        x = r.get(t) or {}
        if "error" not in x and x.get("tok"): usage.append((t, x["tok"], x.get("ms")))
for p in [f"{H}/batch2/labels.json", f"{H}/batch2/gi/labels.json"]:
    d = load(p)
    if not isinstance(d, list): continue
    n = 0; tag = "batch2" + ("-govinfo" if "/gi/" in p else "")
    for c in d:
        for o in c.get("rulings") or [c]:
            n += 1
            rows.append({"batch": tag, "id": o.get("opinion_key") or c.get("id"), "case": c.get("case_name"), "court": c.get("court"), "date": o.get("date_filed"),
                "claim": N(c.get("claim_type")), "dct": N(o.get("decisions_claim_type")), "jct": N(o.get("jev_claim_type")),
                "d": N(o.get("decisions_outcome")), "j": N(o.get("jev_outcome")), "final": N(o.get("outcome_final")) if o.get("label_status") != "model_agreed" else None,
                "status": o.get("label_status"), "url": o.get("url") or o.get("opinion_url"), "docket": c.get("docket_id")})
    sources.append(f"{os.path.relpath(p, H)} ({n})")
    raw = load(os.path.join(os.path.dirname(p), "raw_labels.json"))
    for r in (raw.values() if isinstance(raw, dict) else raw or []):
        for t in P:
            x = (r or {}).get(t) or {}
            if isinstance(x, dict) and "error" not in x and x.get("tok"): usage.append((t, x["tok"], x.get("ms")))
for r in rows: r["agree"] = bool(r["d"] and r["d"] == r["j"])
both = [r for r in rows if r["d"] and r["j"]]; gt = [r for r in rows if r["final"]]
def acc(k): return (sum(r[k] == r["final"] for r in gt), len(gt))
cost = {}
for t in P:
    u = [x for x in usage if x[0] == t]; ms = sorted(x[2] for x in u if x[2])
    cost[t] = {"calls": len(u), "per1k": (sum(x[1] for x in u) / len(u) * P[t] / 1e6 * 1000) if u else None, "median_ms": ms[len(ms)//2] if ms else None,
               "acc": acc("d" if t == "decisions" else "j")}
summary = {"n": len(rows), "cases": len({r["docket"] or r["id"] for r in rows}), "agree": sum(r["agree"] for r in both), "both": len(both),
    "ct_agree": sum(r["dct"] == r["jct"] for r in rows if r["dct"]), "ct_n": sum(1 for r in rows if r["dct"]), "gt": len(gt), "cost": cost,
    "built": datetime.datetime.now().strftime("%b %d, %Y %I:%M %p ET"), "sources": sources}
tpl = open(f"{H}/dashboard/template.html").read()
out = tpl.replace("/*DATA*/null", json.dumps({"rows": rows, "summary": summary}).replace("</", "<\\/"))
open(f"{H}/dashboard/index.html", "w").write(out)
print(f"{len(rows)} rulings, agreement {summary['agree']}/{summary['both']}, ground truth {len(gt)}, cost/1k {{d: {cost['decisions']['per1k']}, j: {cost['jev']['per1k']}}} sources {sources}")
