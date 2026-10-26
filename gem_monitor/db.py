import json, sqlite3
from pathlib import Path
from contextlib import contextmanager
from .config import settings

@contextmanager
def connect():
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(settings.db_path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    try:
        yield db
        db.commit()
    finally: db.close()

def init_db():
    with connect() as d:
        d.executescript("""
        CREATE TABLE IF NOT EXISTS urls(url TEXT PRIMARY KEY, depth INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'queued', last_checked TEXT, last_error TEXT);
        CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY, started TEXT NOT NULL, finished TEXT, status TEXT NOT NULL, checked INTEGER DEFAULT 0, skipped INTEGER DEFAULT 0, failed INTEGER DEFAULT 0, error TEXT);
        CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY, url TEXT NOT NULL, keyword TEXT NOT NULL, context_key TEXT NOT NULL, context TEXT NOT NULL, fingerprint TEXT NOT NULL, present INTEGER NOT NULL DEFAULT 1, updated TEXT NOT NULL, UNIQUE(url,keyword,context_key));
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, idem_key TEXT UNIQUE NOT NULL, type TEXT NOT NULL, url TEXT NOT NULL, keyword TEXT NOT NULL, old_context TEXT, new_context TEXT NOT NULL, created TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS scheduler_lock(name TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL);
        """)
        for row in json.loads(Path("keywords.json").read_text(encoding="utf-8")):
            d.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", ("keyword:"+row["term"], json.dumps(row)))
