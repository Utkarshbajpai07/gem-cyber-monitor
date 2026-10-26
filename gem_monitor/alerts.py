import hashlib, json, time
from datetime import datetime, timezone
import msal, requests
from .config import settings
from .db import connect

def utcnow(): return datetime.now(timezone.utc).isoformat()

def upsert_hits(url, hits, baseline=False):
    events=[]; now=utcnow()
    with connect() as d:
        seen=set()
        for h in hits:
            key=(url,h.keyword,h.context_key); seen.add(key)
            old=d.execute("SELECT * FROM matches WHERE url=? AND keyword=? AND context_key=?",key).fetchone()
            typ=None; oldctx=None
            if old is None: typ="new" if not baseline or settings.first_run_policy=="notify" else None
            elif not old["present"]: typ="new"
            elif old["fingerprint"] != h.fingerprint: typ="changed"; oldctx=old["context"]
            d.execute("INSERT INTO matches(url,keyword,context_key,context,fingerprint,present,updated) VALUES(?,?,?,?,?,1,?) ON CONFLICT(url,keyword,context_key) DO UPDATE SET context=excluded.context,fingerprint=excluded.fingerprint,present=1,updated=excluded.updated",(*key,h.context,h.fingerprint,now))
            if typ:
                idem=hashlib.sha256(f"{typ}|{url}|{h.keyword}|{h.context_key}|{h.fingerprint}".encode()).hexdigest()
                d.execute("INSERT OR IGNORE INTO alerts(idem_key,type,url,keyword,old_context,new_context,created) VALUES(?,?,?,?,?,?,?)",(idem,typ,url,h.keyword,oldctx,h.context,now))
        # Removal only follows successful page parsing.
        for row in d.execute("SELECT id,url,keyword,context_key FROM matches WHERE url=? AND present=1",(url,)).fetchall():
            if (row["url"],row["keyword"],row["context_key"]) not in seen:
                d.execute("UPDATE matches SET present=0,updated=? WHERE id=?",(now,row["id"]))
    return events

def send_pending(limit=20):
    if not (settings.ms_client_id and settings.ms_sender_email and settings.recipient_email): return 0
    app=msal.PublicClientApplication(settings.ms_client_id,authority=f"https://login.microsoftonline.com/{settings.ms_tenant_id}")
    scopes=["https://graph.microsoft.com/Mail.Send"]
    result=app.acquire_token_silent(scopes,account=None)
    if not result:
        flow=app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow: raise RuntimeError("Microsoft device-code flow could not start")
        print(flow["message"])
        result=app.acquire_token_by_device_flow(flow)
    if "access_token" not in result: raise RuntimeError(result.get("error_description","Microsoft authentication failed"))
    token=result["access_token"]; sent=0
    with connect() as d: rows=d.execute("SELECT * FROM alerts WHERE status='pending' ORDER BY id LIMIT ?",(limit,)).fetchall()
    for a in rows:
        body=f"Alert: {a['type']} keyword match\nKeyword: {a['keyword']}\nDomain: gem.gov.in\nSource URL: {a['url']}\n\nCurrent context:\n{a['new_context']}\n\nPrevious context:\n{a['old_context'] or '(none)'}"
        payload={"message":{"subject":f"GeM {a['type']} match: {a['keyword']}","body":{"contentType":"Text","content":body},"toRecipients":[{"emailAddress":{"address":settings.recipient_email}}]},"saveToSentItems":"true"}
        try:
            r=requests.post(f"https://graph.microsoft.com/v1.0/users/{settings.ms_sender_email}/sendMail",headers={"Authorization":f"Bearer {token}"},json=payload,timeout=30)
            r.raise_for_status()
            with connect() as d: d.execute("UPDATE alerts SET status='sent',attempts=attempts+1,last_error=NULL WHERE id=?",(a["id"],))
            sent+=1
        except requests.RequestException as e:
            with connect() as d: d.execute("UPDATE alerts SET attempts=attempts+1,last_error=? WHERE id=?",(str(e),a["id"]))
    return sent
