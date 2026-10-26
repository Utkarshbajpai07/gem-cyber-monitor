import ipaddress, socket, time
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from .config import settings

DROP_PARAMS = {"page", "offset", "sort", "sid", "sessionid"}

def normalize_url(url: str) -> str:
    p=urlsplit(url.strip())
    scheme=p.scheme.lower()
    host=(p.hostname or "").lower()
    if p.port and not ((scheme=="https" and p.port==443) or (scheme=="http" and p.port==80)): host += f":{p.port}"
    path=p.path or "/"
    if path != "/": path=path.rstrip("/")
    query=urlencode([(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in DROP_PARAMS])
    return urlunsplit((scheme,host,path,query,""))

def allowed(url: str, scope: str = settings.domain_scope) -> bool:
    try:
        p=urlsplit(url)
        if p.scheme != "https" or not p.hostname or p.username or p.password: return False
        host=p.hostname.lower().rstrip(".")
        if not (host == scope.lower() or host.endswith("."+scope.lower())): return False
        # Reject literal IPs and DNS answers resolving to non-public addresses (SSRF protection).
        try:
            ip=ipaddress.ip_address(host)
            return ip.is_global
        except ValueError: pass
        for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
            if not ipaddress.ip_address(result[4][0]).is_global: return False
        return True
    except (ValueError, OSError): return False

class Crawler:
    def __init__(self):
        self.session=requests.Session(); self.session.headers.update({"User-Agent":"GeM-Cyber-Monitor/0.1 (polite public-page monitor)"})
        self.robots={}
    def can_fetch(self, url):
        p=urlsplit(url); origin=f"{p.scheme}://{p.netloc}"
        if origin not in self.robots:
            rp=RobotFileParser(); rp.set_url(origin+"/robots.txt")
            try:
                r=self.session.get(origin+"/robots.txt",timeout=settings.timeout,allow_redirects=False)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                elif r.status_code == 404:
                    rp.parse([])
                else:
                    return False
            except requests.RequestException: return False
            self.robots[origin]=rp
        return self.robots[origin].can_fetch(self.session.headers["User-Agent"], url)
    def fetch(self, url):
        current=url
        for _ in range(6):
            if not allowed(current): raise ValueError("URL rejected by domain or public-IP policy")
            if not self.can_fetch(current): raise PermissionError("robots.txt disallows URL or could not be checked")
            last_error=None
            for attempt in range(max(1, settings.retries)):
                try:
                    r=self.session.get(current, timeout=settings.timeout, allow_redirects=False)
                    last_error=None
                    break
                except requests.RequestException as exc:
                    last_error=exc
                    if attempt + 1 >= max(1, settings.retries): raise
                    time.sleep(min(2 ** attempt, 8))
            if last_error: raise last_error
            if r.is_redirect or r.is_permanent_redirect:
                nxt=urljoin(current,r.headers.get("Location",""))
                if not allowed(nxt): raise ValueError("Redirect outside permitted public GeM domain")
                current=nxt; continue
            r.raise_for_status()
            if "text/html" not in r.headers.get("Content-Type", "").lower(): return r.url, "", []
            soup=BeautifulSoup(r.text,"html.parser")
            for tag in soup(["script","style","noscript","svg"]): tag.decompose()
            text="\n".join(x.strip() for x in soup.stripped_strings)
            links=[]
            for a in soup.select("a[href]"):
                u=normalize_url(urljoin(r.url,a["href"]))
                if allowed(u): links.append(u)
            if settings.enable_playwright and len(text)<100:
                text=self._render(current) or text
            time.sleep(settings.delay)
            return normalize_url(r.url),text,links
        raise ValueError("Too many redirects")
    def _render(self,url):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError: return None
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page()
            try:
                page.goto(url,wait_until="domcontentloaded",timeout=settings.playwright_timeout_ms)
                return page.locator("body").inner_text(timeout=settings.playwright_timeout_ms)
            finally: browser.close()
