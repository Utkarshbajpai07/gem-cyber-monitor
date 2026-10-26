import json, time, uuid
from datetime import datetime, timezone
from .config import settings
from .db import connect
from .crawler import Crawler, normalize_url
from .matching import find_matches
from .alerts import upsert_hits, send_pending

def now(): return datetime.now(timezone.utc).isoformat()

def enqueue(url,depth):
    with connect() as d: d.execute("INSERT OR IGNORE INTO urls(url,depth) VALUES(?,?)",(normalize_url(url),depth))

def scan():
    owner=str(uuid.uuid4()); ts=now()
    with connect() as d:
        # Transactional lock prevents overlapping scans across processes.
        if not d.execute("INSERT OR IGNORE INTO scheduler_lock(name,owner,expires) VALUES('scan',?,?)",(owner,time.time()+3600)).rowcount:
            raise RuntimeError("A scan is already running")
        cur=d.execute("INSERT INTO scans(started,status) VALUES(?,'running')",(ts,)); scan_id=cur.lastrowid
    checked=skipped=failed=0; errors=[]; crawler=Crawler()
    enqueue(settings.root_url,0)
    try:
        # Rotate through previously checked URLs by oldest check time so each run
        # revisits a bounded slice while newly discovered links enter the same queue.
        with connect() as d: queue=d.execute("SELECT * FROM urls WHERE status IN ('queued','failed','done') ORDER BY last_checked IS NOT NULL, last_checked, depth LIMIT ?",(settings.max_pages,)).fetchall()
        with connect() as d: total=d.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        baseline=total==0
        with connect() as d:
            keywords=[json.loads(r[0]) for r in d.execute("SELECT value FROM settings WHERE key LIKE 'keyword:%'")]
        for row in queue:
            if row["depth"]>settings.max_depth:
                skipped+=1; continue
            try:
                durl,text,links=crawler.fetch(row["url"])
                checked+=1
                if text: upsert_hits(durl,find_matches(text,keywords),baseline)
                with connect() as d: d.execute("UPDATE urls SET status='done',last_checked=?,last_error=NULL WHERE url=?",(now(),row["url"]))
                for link in links: enqueue(link,row["depth"]+1)
            except PermissionError as e:
                skipped+=1
                with connect() as d: d.execute("UPDATE urls SET status='skipped',last_checked=?,last_error=? WHERE url=?",(now(),str(e),row["url"]))
            except Exception as e:
                failed+=1; errors.append(f"{row['url']}: {e}")
                with connect() as d: d.execute("UPDATE urls SET status='failed',last_checked=?,last_error=? WHERE url=?",(now(),str(e),row["url"]))
        send_pending()
        with connect() as d: d.execute("UPDATE scans SET finished=?,status=?,checked=?,skipped=?,failed=?,error=? WHERE id=?",(now(),"partial" if failed else "completed",checked,skipped,failed,"\n".join(errors)[:4000] or None,scan_id))
    except Exception as e:
        with connect() as d: d.execute("UPDATE scans SET finished=?,status='failed',error=? WHERE id=?",(now(),str(e),scan_id))
        raise
    finally:
        with connect() as d: d.execute("DELETE FROM scheduler_lock WHERE name='scan' AND owner=?",(owner,))
    return {"scan_id":scan_id,"checked":checked,"skipped":skipped,"failed":failed,"errors":errors}
