import json,os,time,urllib.request,urllib.parse
TOK=open(os.path.expanduser("~/.secrets/courtlistener_token")).read().strip()
B="https://www.courtlistener.com/api/rest/v4/"
def get(url,params=None):
    if params: url+="?"+urllib.parse.urlencode(params)
    if not url.startswith("http"): url=B+url
    for i in range(12):
        try:
            req=urllib.request.Request(url,headers={"Authorization":"Token "+TOK,"User-Agent":"bexperiments research"})
            with urllib.request.urlopen(req,timeout=60) as r: time.sleep(2); return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(int(e.headers.get('retry-after') or 60)+2); continue
            if e.code>=500: time.sleep(5); continue
            raise
    raise RuntimeError("failed "+url[:80])
