import json,os,time,urllib.request,urllib.parse,urllib.error
TOK=open(os.path.expanduser("~/.secrets/courtlistener_token")).read().strip()
B="https://www.courtlistener.com/api/rest/v4/";_last=[0.0];N=[0]
def get(url,params=None):
    if params: url+="?"+urllib.parse.urlencode(params)
    if not url.startswith("http"): url=B+url
    for i in range(30):
        w=4.2-(time.time()-_last[0])
        if w>0: time.sleep(w)
        _last[0]=time.time();N[0]+=1
        try:
            req=urllib.request.Request(url,headers={"Authorization":"Token "+TOK,"User-Agent":"bexperiments research"})
            with urllib.request.urlopen(req,timeout=90) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==429:
                ra=int(e.headers.get("retry-after") or 120); print(f"429 sleeping {ra}s",flush=True); time.sleep(ra+5); continue
            if e.code>=500: time.sleep(30); continue
            raise
        except Exception as e: print("net err",repr(e)[:100],flush=True); time.sleep(30)
    raise RuntimeError("gave up "+url[:100])
