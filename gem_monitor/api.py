from fastapi import FastAPI, HTTPException
from .db import init_db, connect
from .service import scan, enqueue
from .config import settings
import json

app=FastAPI(title="GeM Cybersecurity Monitor",version="0.1.0",description="Incremental monitor for permitted public GeM pages")
@app.on_event("startup")
def startup(): init_db()
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/status")
def status():
    with connect() as d:
        return {"queued":d.execute("SELECT COUNT(*) FROM urls WHERE status='queued'").fetchone()[0],"urls":d.execute("SELECT COUNT(*) FROM urls").fetchone()[0],"interval_minutes":settings.interval_minutes}
@app.post("/scan")
def manual_scan():
    try: return scan()
    except RuntimeError as e: raise HTTPException(409,str(e))
@app.get("/scans")
def scans(limit:int=50):
    with connect() as d: return [dict(r) for r in d.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?",(min(max(limit,1),200),))]
@app.get("/urls")
def urls(limit:int=100):
    with connect() as d: return [dict(r) for r in d.execute("SELECT * FROM urls ORDER BY last_checked DESC LIMIT ?",(min(max(limit,1),500),))]
@app.get("/matches")
def matches(limit:int=100):
    with connect() as d: return [dict(r) for r in d.execute("SELECT * FROM matches ORDER BY updated DESC LIMIT ?",(min(max(limit,1),500),))]
@app.get("/alerts")
def alerts(limit:int=100):
    with connect() as d: return [dict(r) for r in d.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?",(min(max(limit,1),500),))]
@app.get("/keywords")
def keywords():
    with connect() as d: return [json.loads(r[0]) for r in d.execute("SELECT value FROM settings WHERE key LIKE 'keyword:%'")]
@app.put("/keywords/{term}")
def update_keyword(term:str, payload:dict):
    if payload.get("mode") not in ("word","phrase") or "enabled" not in payload: raise HTTPException(400,"mode and enabled are required")
    with connect() as d:
        key="keyword:"+term
        if not d.execute("SELECT 1 FROM settings WHERE key=?",(key,)).fetchone(): raise HTTPException(404,"Unknown keyword")
        d.execute("UPDATE settings SET value=? WHERE key=?",(json.dumps({"term":term,"mode":payload["mode"],"enabled":bool(payload["enabled"])}),key))
    return {"updated":term}
