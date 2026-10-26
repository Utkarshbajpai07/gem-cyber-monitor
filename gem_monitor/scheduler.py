import time, logging
from .db import init_db
from .service import scan
from .config import settings

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
if __name__=="__main__":
    init_db(); logging.info("Scheduler running every %s minutes",settings.interval_minutes)
    while True:
        try: scan()
        except Exception: logging.exception("Scheduled scan failed")
        time.sleep(settings.interval_minutes*60)
