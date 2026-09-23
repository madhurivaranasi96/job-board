"""Deterministic visa / sponsorship classification. Never fabricates."""

from __future__ import annotations

import re
from typing import Iterable

VISA_LABELS = {
    "available": "Sponsorship Available",
    "likely": "Sponsorship Likely",
    "unknown": "Visa sponsorship: Unknown",
    "none": "No Sponsorship",
    "auth_required": "Existing Work Authorization Required",
    "not_applicable": "Not Applicable / Remote",
}

AVAILABLE = [
    r"\bvisa sponsorships?\b",
    r"\bsponsors? (?:h-?1-?b|visas?|work visas?)\b",
    r"\b(?:we|company|employer) (?:will|can|does|do) sponsor\b",
    r"\bwill sponsor\b",
    r"\bsponsorship available\b",
    r"\bopen to sponsoring\b",
    r"\bwork visa\b",
    r"\bh-?1-?b(?:\s+transfer)?\b",
    r"\bgreen card sponsorship\b",
    r"\bskilled worker(?: visa)?\b",
    r"\buk skilled worker\b",
    r"\beu blue card\b",
    r"\b(?:european )?blue card\b",
    r"\bgermany work visa\b",
    r"\bhighly skilled migrant\b",
    r"\bkennismigrant\b",
    r"\bcanada work permit\b",
    r"\blmia\b",
    r"\baustralia(?:n)? (?:employer )?sponsorship\b",
    r"\b(?:subclass )?482\b",
    r"\bnew zealand sponsorship\b",
    r"\brelocation sponsorship\b",
    r"\bimmigration support\b",
    r"\bvisa support (?:is )?available\b",
    r"\bsponsorship (?:is )?provided\b",
    r"\bwe sponsor\b",
]

LIKELY = [
    r"\brelocation (?:assistance|support|package|bonus)\b",
    r"\bimmigration assistance\b",
    r"\bvisa assistance\b",
    r"\bhelp with (?:a |your )?visa\b",
    r"\binternational candidates (?:are )?welcome\b",
    r"\bapplications from (?:anywhere|worldwide|all countries)\b",
    r"\brelocation available\b",
    r"\bglobal mobility\b",
]

NONE = [
    r"\bno visa sponsorship\b",
    r"\bnot able to sponsor\b",
    r"\bcannot sponsor\b",
    r"\bcan'?t sponsor\b",
    r"\bwill not sponsor\b",
    r"\bunable to sponsor\b",
    r"\bsponsorship is not available\b",
    r"\bdoes not sponsor\b",
    r"\bdo not sponsor\b",
    r"\bunable to provide (?:visa |work )?sponsorship\b",
    r"\bno sponsorships?\b",
    r"\bnot offering sponsorship\b",
    r"\bno h-?1-?b\b",
    r"\bdo not provide visa\b",
    r"\bdoes not provide visa\b",
    r"\bno visa assistance\b",
    r"\bnot provide visa assistance\b",
]

AUTH = [
    r"\bmust be authorized to work\b",
    r"\bmust have (?:existing )?work authorization\b",
    r"\bwork authorization (?:is )?required\b",
    r"\bus citizenship required\b",
    r"\bu\.?s\.? persons? only\b",
    r"\bgreen card or citizen\b",
    r"\bgc/usc\b",
    r"\bonly (?:us|u\.s\.) (?:citizens|persons|applicants)\b",
    r"\beligible to work without sponsorship\b",
    r"\bunrestricted work authorization\b",
    r"\bmust already be (?:eligible|authorized) to work\b",
    r"\bcandidates must be able to work without\b",
]

ANYWHERE = [
    r"\bwork from anywhere\b",
    r"\banywhere in the world\b",
    r"\bworldwide remote\b",
    r"\bno location restriction\b",
    r"\bremote[- ](?:worldwide|anywhere|global)\b",
]


def _snippets(text: str, patterns: Iterable[str], limit: int = 3) -> list[str]:
    found: list[str] = []
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if not m:
            continue
        start = max(0, m.start() - 48)
        end = min(len(text), m.end() + 48)
        snip = re.sub(r"\s+", " ", text[start:end]).strip()
        if snip and snip not in found:
            found.append(snip)
        if len(found) >= limit:
            break
    return found


def classify_visa(text: str, work_arrangement: str, country_code: str) -> dict:
    hay = text or ""
    none_hits = _snippets(hay, NONE)
    auth_hits = _snippets(hay, AUTH)
    avail_hits = _snippets(hay, AVAILABLE)
    likely_hits = _snippets(hay, LIKELY)
    anywhere_hits = _snippets(hay, ANYWHERE)

    if none_hits and not avail_hits:
        status = "auth_required" if auth_hits else "none"
        evidence = (none_hits + auth_hits)[:4]
        return {"status": status, "evidence": evidence, "label": VISA_LABELS[status]}
    if avail_hits:
        return {"status": "available", "evidence": avail_hits, "label": VISA_LABELS["available"]}
    if auth_hits and not likely_hits:
        return {"status": "auth_required", "evidence": auth_hits, "label": VISA_LABELS["auth_required"]}
    if likely_hits:
        return {"status": "likely", "evidence": likely_hits, "label": VISA_LABELS["likely"]}
    if work_arrangement == "remote" and (
        anywhere_hits or country_code in {"XX", "REMOTE", ""} or re.search(r"worldwide|anywhere|global", hay[:800], re.I)
    ):
        if anywhere_hits or re.search(r"worldwide|anywhere|global", hay[:800], re.I):
            return {
                "status": "not_applicable",
                "evidence": anywhere_hits
                or ["Remote / worldwide posting — no visa language found"],
                "label": VISA_LABELS["not_applicable"],
            }
    return {"status": "unknown", "evidence": [], "label": VISA_LABELS["unknown"]}
