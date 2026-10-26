from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    root_url: str = os.getenv("GEM_ROOT_URL", "https://gem.gov.in/")
    domain_scope: str = os.getenv("GEM_DOMAIN_SCOPE", "gem.gov.in")
    interval_minutes: int = int(os.getenv("CHECK_INTERVAL_MINUTES", "15"))
    max_pages: int = int(os.getenv("MAX_PAGES_PER_RUN", "100"))
    max_depth: int = int(os.getenv("MAX_CRAWL_DEPTH", "3"))
    timeout: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    delay: float = float(os.getenv("REQUEST_DELAY_SECONDS", "2"))
    retries: int = int(os.getenv("MAX_RETRIES", "3"))
    db_path: str = os.getenv("DATABASE_PATH", "data/monitor.sqlite3")
    first_run_policy: str = os.getenv("FIRST_RUN_POLICY", "notify").lower()
    enable_playwright: bool = os.getenv("ENABLE_PLAYWRIGHT", "false").lower() == "true"
    playwright_timeout_ms: int = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "15000"))
    ms_client_id: str = os.getenv("MS_CLIENT_ID", "")
    ms_tenant_id: str = os.getenv("MS_TENANT_ID", "common")
    ms_client_secret: str = os.getenv("MS_CLIENT_SECRET", "")
    ms_sender_email: str = os.getenv("MS_SENDER_EMAIL", "")
    recipient_email: str = os.getenv("ALERT_RECIPIENT_EMAIL", "")

settings = Settings()
