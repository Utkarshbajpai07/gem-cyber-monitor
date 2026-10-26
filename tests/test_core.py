from gem_monitor.crawler import normalize_url, allowed
from gem_monitor.matching import find_matches

def test_normalize_url():
    assert normalize_url("https://GEM.gov.in/a/?page=3#x")=="https://gem.gov.in/a"

def test_allowlist(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(None,None,None,None,("8.8.8.8",443))])
    assert allowed("https://gem.gov.in/")
    assert allowed("https://x.gem.gov.in/")
    assert not allowed("https://evilgem.gov.in/")
    assert not allowed("http://gem.gov.in/")

def test_keyword_whole_word_and_case():
    kw=[{"term":"WAF","mode":"word"},{"term":"Web Application Firewall","mode":"phrase"}]
    hits=find_matches("A WAF test. waf inside. Web application firewall here. SWAF no.",kw)
    assert [(h.keyword,h.count) for h in hits]==[("WAF",2),("Web Application Firewall",1)]

def test_match_fingerprint_changes_with_context():
    kw=[{"term":"EDR","mode":"word"}]
    a=find_matches("EDR required",kw)[0]; b=find_matches("Advanced EDR required",kw)[0]
    assert a.fingerprint != b.fingerprint

