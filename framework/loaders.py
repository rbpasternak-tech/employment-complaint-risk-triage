"""Dataset loaders. Each yields dicts: {doc_id, motion_id, text}. Register new ones in LOADERS."""
import json, os, re

def excerpt(t):
    """Same excerpting rule as label.py: 12(b)(6) paragraphs + last 24k chars, capped at 60k."""
    tail = t[-24000:]; head = t[:-24000]
    paras = [p for p in re.split(r"\n\s*\n|(?<=\.)\s{2,}", head) if "12(b)(6)" in p]
    ex = "\n\n".join(paras)[:30000] + "\n\n[...]\n\n" + tail if paras else (t[:6000] + "\n\n[...]\n\n" + tail if head else t)
    return ex[:60000]

def litigation_cases(index, text_dir):
    for m in json.load(open(index)):
        p = os.path.join(text_dir, f"{m['id']}.txt")
        if not os.path.exists(p): continue
        t = open(p).read()
        if len(t) < 300: continue
        yield {"doc_id": m["id"], "motion_id": f"{m['id']}-m1", "text": excerpt(t)}

def jsonl(path, id_field="id", text_field="text", motion_suffix="-m1"):
    """Generic: one JSON object per line. Good for exports from legal_ingest or public.documents."""
    for line in open(path):
        d = json.loads(line)
        yield {"doc_id": d[id_field], "motion_id": f"{d[id_field]}{motion_suffix}", "text": d[text_field][:60000]}

LEAK_MARKERS = re.compile(r"IT IS (HEREBY )?ORDERED|motion to dismiss is (GRANTED|DENIED)|MEMORANDUM (OPINION|AND ORDER)|REPORT AND RECOMMENDATION", re.I)
INPUT_KINDS = {"complaint", "amended_complaint", "demand_letter"}

def complaints(index, text_dir, kinds=None):
    """Risk-triage input: complaint / demand-letter text ONLY. index = JSON list of
    {filing_id, matter_id, filing_kind, path}. Rulings and motions are refused (no outcome leakage)."""
    kinds = set(kinds or INPUT_KINDS)
    assert kinds <= INPUT_KINDS, f"non-input filing kinds requested: {kinds - INPUT_KINDS}"
    for m in json.load(open(index)):
        if m.get("filing_kind") not in kinds: continue
        t = open(os.path.join(text_dir, m["path"])).read()
        if len(t) < 300: continue
        if LEAK_MARKERS.search(t[:20000]):
            raise ValueError(f"{m['filing_id']}: text looks like a court order/opinion; refusing (leakage guard)")
        yield {"doc_id": m["matter_id"], "motion_id": m["filing_id"], "text": t[:60000]}

LOADERS = {"litigation_cases": litigation_cases, "jsonl": jsonl, "complaints": complaints}
