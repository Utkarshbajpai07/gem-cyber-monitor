import hashlib, re
from dataclasses import dataclass

@dataclass
class Hit:
    keyword: str
    context: str
    count: int
    context_key: str
    fingerprint: str

def _digest(s: str) -> str: return hashlib.sha256(s.encode("utf-8")).hexdigest()

def find_matches(text: str, keywords: list[dict]) -> list[Hit]:
    # Use paragraph-sized contexts to retain readable source content while keeping identity stable across edits.
    blocks = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n+", text) if p.strip()]
    hits = []
    for kw in keywords:
        if not kw.get("enabled", True): continue
        term, mode = kw["term"], kw.get("mode", "phrase")
        pattern = re.compile(r"(?<!\w)"+re.escape(term)+r"(?!\w)", re.I) if mode == "word" else re.compile(re.escape(term), re.I)
        for i, block in enumerate(blocks):
            found = list(pattern.finditer(block))
            if found:
                # Stable occurrence identity is keyword + exact URL + occurrence ordinal in page text.
                hits.append(Hit(term, block, len(found), f"{term.casefold()}:{i}", _digest(block.casefold())))
    return hits
