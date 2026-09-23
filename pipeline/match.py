"""Deterministic resume match. Weights: skills 40, title 20, exp 15, domain 10, loc 10, visa 5."""

from __future__ import annotations

import re
from .profile import PROFILE

CORE_SKILLS = ["C#", ".NET", "Angular", "JavaScript", "TypeScript", "Web API", "REST", "ASP.NET"]

TECH_PATTERNS = [
    (r"(?<![a-z])(?:c\s*#|csharp)\b", "C#"),
    (r"(?<![a-z])(?:\.net|dotnet|asp\.?\s*net)\b", ".NET"),
    (r"\basp\.?\s*net\b", "ASP.NET"),
    (r"\bweb\s*apis?\b", "Web API"),
    (r"\bangularjs\b|\bangular\.js\b", "AngularJS"),
    (r"\bangular\b(?!\s*js)", "Angular"),
    (r"\btypescript\b", "TypeScript"),
    (r"\bjavascript\b", "JavaScript"),
    (r"\brest(?:ful)?(?:\s+apis?)?\b", "REST"),
    (r"\bsql\b|postgresql|mssql|\btsql\b", "SQL"),
    (r"\bazure\b", "Azure"),
    (r"\baws\b|amazon web services", "AWS"),
    (r"\bagentic\b", "Agentic AI"),
    (r"\bllms?\b|large language models?", "LLM"),
    (r"\breact\b", "React"),
    (r"\bnode\.?js\b", "Node.js"),
    (r"\bpython\b", "Python"),
    (r"\bjava\b(?!\s*script)", "Java"),
]


def extract_technologies(text: str) -> list[str]:
    hay = f" {text} "
    found: list[str] = []
    for pat, label in TECH_PATTERNS:
        if re.search(pat, hay, re.I) and label not in found:
            found.append(label)
    return found


def extract_experience(text: str) -> tuple[int | None, int | None, str]:
    t = text or ""
    m = re.search(r"(\d+)\s*[-–to]+\s*(\d+)\s*\+?\s*years?", t, re.I)
    if m:
        return int(m.group(1)), int(m.group(2)), f"{m.group(1)}–{m.group(2)} years"
    m = re.search(r"(\d+)\s*\+\s*years?", t, re.I)
    if m:
        return int(m.group(1)), None, f"{m.group(1)}+ years"
    m = re.search(r"(?:minimum|at least|min\.?)\s*(\d+)\s*years?", t, re.I)
    if m:
        return int(m.group(1)), None, f"{m.group(1)}+ years"
    if re.search(r"\bprincipal\b|\bstaff\b|\barchitect\b", t, re.I):
        return 8, None, "Staff / Principal"
    if re.search(r"\bsenior\b|\bsr\.?\b", t, re.I):
        return 5, None, "Senior"
    if re.search(r"\bjunior\b|\bentry[- ]level\b", t, re.I):
        return 0, 2, "Junior"
    return None, None, ""


def extract_industry(text: str) -> str:
    t = text.lower()
    if re.search(r"\batm\b|payments?|ndc|ndce", t):
        return "ATM / Payments"
    if re.search(r"\bbanking\b|\bbank\b", t):
        return "Banking"
    if "fintech" in t:
        return "FinTech"
    if re.search(r"financial services|\bfinance\b|\binsurance\b", t):
        return "Financial Services"
    if "enterprise" in t:
        return "Enterprise Software"
    return "Technology"


def _title_match(title: str) -> tuple[bool, str, int]:
    t = title.lower()
    preferred = PROFILE["preferred_titles"]
    for pref in preferred:
        key = pref.lower()
        tokens = [x for x in re.split(r"\s+", key) if len(x) > 2]
        if key in t or (tokens and all(tok in t for tok in tokens[:2])):
            boost = 2 if re.search(r"\bsenior\b|\bsr\.?\b", t) else 0
            return True, pref, 18 + boost
    if re.search(r"software (engineer|developer)|full[- ]stack|backend|frontend", t):
        return True, "Adjacent software engineering title", 10
    return False, "", 0


def score_job(job: dict) -> dict:
    hay = " ".join(
        [
            job.get("title") or "",
            job.get("company") or "",
            job.get("location") or "",
            job.get("description") or "",
            " ".join(job.get("technologies") or []),
        ]
    ).lower()
    reasons: list[str] = []
    missing: list[str] = []
    concerns: list[str] = []
    score = 0

    job_tech = set(job.get("technologies") or []) | set(extract_technologies(hay))
    skill_pts = 0
    hits: list[str] = []
    for skill in CORE_SKILLS:
        present = skill in job_tech or skill.lower() in hay
        if skill == "C#" and re.search(r"c#|csharp|c sharp", hay):
            present = True
        if skill == ".NET" and re.search(r"\.net|dotnet|asp\.net", hay):
            present = True
        if present:
            skill_pts += 5
            hits.append(skill)
    for skill in PROFILE["preferred_technologies"]:
        if skill in CORE_SKILLS:
            continue
        if (skill in job_tech or skill.lower() in hay) and skill_pts < 40:
            skill_pts += 2
            hits.append(skill)
    score += min(40, skill_pts)
    reasons.extend(hits[:8])

    extras = ["React", "Python", "Java", "Go", "Kotlin"]
    profile_set = {s.lower() for s in PROFILE["skills"]}
    for tech in job_tech:
        if tech in extras and tech.lower() not in profile_set and tech not in missing:
            missing.append(tech)
    if re.search(r"\bazure\b", hay) and "azure" not in profile_set:
        missing.append("Azure")
    if re.search(r"\baws\b", hay) and "aws" not in profile_set:
        missing.append("AWS")
    if re.search(r"\breact\b", hay) and "react" not in profile_set and "React" not in missing:
        missing.append("React")

    hit, reason, weight = _title_match(job.get("title") or "")
    score += min(20, weight)
    if hit:
        reasons.append(reason)
    else:
        concerns.append("Title is outside the usual preferred set")

    years = PROFILE["years_experience"]
    need = job.get("experienceYearsMin")
    if need is None:
        score += 10
    elif years >= need:
        score += 15
        reasons.append(f"{years}+ years experience")
    elif years + 1 >= need:
        score += 8
        concerns.append(f"Role asks for {need}+ years")
    else:
        score += 2
        concerns.append(f"Role asks for {need}+ years")

    domain = 0
    for kw in PROFILE["domain_keywords"]:
        if kw.lower() in hay:
            domain += 4
            reasons.append(kw.title() + " domain")
    for ind in PROFILE["preferred_industries"]:
        if ind.lower() in hay or ind.lower() in (job.get("industry") or "").lower():
            domain += 3
    score += min(10, domain)

    loc = 0
    arr = job.get("workArrangement") or ""
    country = job.get("country") or ""
    code = job.get("countryCode") or ""
    if arr == "remote":
        loc += 10
        reasons.append("Remote eligible")
    elif any(c.lower() in country.lower() for c in PROFILE["preferred_countries"] if country):
        loc += 9 if PROFILE["relocation"] else 5
        if country:
            reasons.append(country)
    elif code == "IN":
        loc += 8
        reasons.append("India")
    elif PROFILE["relocation"]:
        loc += 4
    else:
        loc += 1
    score += min(10, loc)

    visa = job.get("visaStatus") or "unknown"
    if PROFILE["visa_preference"] == "sponsorship":
        if visa == "available":
            score += 5
            reasons.append("Visa sponsorship mentioned")
        elif visa in {"likely", "not_applicable"}:
            score += 3
        elif visa == "unknown":
            score += 2
        else:
            concerns.append("Employer may not sponsor a work visa")
    else:
        score += 3

    uniq = []
    for r in reasons:
        if r not in uniq:
            uniq.append(r)
    miss = []
    for m in missing:
        if m not in miss:
            miss.append(m)
    cons = []
    for c in concerns:
        if c not in cons:
            cons.append(c)
    return {
        "matchScore": max(0, min(100, int(round(score)))),
        "matchReasons": uniq[:8],
        "missingRequirements": miss[:6],
        "concerns": cons[:5],
    }
