#!/usr/bin/env python3
"""Rolefit fetch — prioritizes India + software roles from public Greenhouse/Lever APIs."""
from __future__ import annotations
import hashlib, html, json, re, sys, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pipeline.profile import PROFILE, TITLE_DROP, TITLE_KEEP
from pipeline.visa import classify_visa
from pipeline.match import extract_experience, extract_industry, extract_technologies, score_job

UA = "RolefitJobBoard/1.0 (+https://github.com/madhurivaranasi96/job-board)"
TIMEOUT = 18
MAX_JOBS_OUT = 500
INDIA_RESERVE = 100
CACHE_PATH = ROOT / "pipeline" / ".cache.json"
NOW = datetime.now(timezone.utc)
NOW_ISO = NOW.isoformat()

GREENHOUSE_BOARDS = [
    "databricks", "okta", "mongodb", "stripe", "rubrik", "gitlab", "bitwarden",
    "fivetran", "toast", "hackerrank", "commvault", "elastic", "twilio", "druva",
    "coinbase", "datadog", "jumio", "adyen", "airbnb", "pingidentity", "groww",
    "sezzle", "sumologic", "karat", "thoughtworks", "mixpanel", "turing",
    "amplitude", "salesloft", "vonage", "labelbox", "cloudflare", "figma",
    "vercel", "anthropic", "scaleai", "freshworks", "browserstack", "postman",
    "chargebee", "epam", "globant", "accenture", "capgemini", "persistent",
    "atlassian", "microsoft", "google", "amazon", "uber", "salesforce",
    "intuit", "paypal", "visa", "mastercard", "jpmorganchase", "americanexpress",
    "snowflake", "hashicorp", "snyk", "crowdstrike", "1password", "hubspot",
    "zendesk", "intercom", "notion", "asana", "rippling", "deel", "remotecom",
]

LEVER_COMPANIES = ["cred", "turing", "sentry", "palantir", "spotify", "rippling", "deel", "remote", "brex", "ramp"]
ASHBY_ORGS = ["openai", "anthropic", "linear", "ramp", "vercel", "notion", "cursor", "perplexity"]

CITY_COUNTRY = {
    "hyderabad": ("Hyderabad", "IN", "India", "south-asia", "Telangana"),
    "bengaluru": ("Bengaluru", "IN", "India", "south-asia", "Karnataka"),
    "bangalore": ("Bengaluru", "IN", "India", "south-asia", "Karnataka"),
    "chennai": ("Chennai", "IN", "India", "south-asia", "Tamil Nadu"),
    "pune": ("Pune", "IN", "India", "south-asia", "Maharashtra"),
    "mumbai": ("Mumbai", "IN", "India", "south-asia", "Maharashtra"),
    "delhi": ("Delhi", "IN", "India", "south-asia", ""),
    "gurgaon": ("Gurugram", "IN", "India", "south-asia", ""),
    "gurugram": ("Gurugram", "IN", "India", "south-asia", ""),
    "noida": ("Noida", "IN", "India", "south-asia", ""),
}
COUNTRY_ALIAS = {
    "india": ("IN", "India", "south-asia"), "usa": ("US", "United States", "north-america"),
    "us": ("US", "United States", "north-america"), "united states": ("US", "United States", "north-america"),
    "canada": ("CA", "Canada", "north-america"), "uk": ("GB", "United Kingdom", "europe"),
    "united kingdom": ("GB", "United Kingdom", "europe"), "remote": ("REMOTE", "Remote", "worldwide"),
    "germany": ("DE", "Germany", "europe"), "ireland": ("IE", "Ireland", "europe"),
    "netherlands": ("NL", "Netherlands", "europe"), "australia": ("AU", "Australia", "asia-pacific"),
    "singapore": ("SG", "Singapore", "asia-pacific"),
}

def log(msg): print(msg, flush=True)

def fetch_json(url, headers=None):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers: h.update(headers)
    try:
        with urlopen(Request(url, headers=h), timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None

def strip_html(text):
    if not text: return ""
    t = html.unescape(html.unescape(text))
    t = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", t)
    t = re.sub(r"(?i)<br\\s*/?>", "\\n", t)
    t = re.sub(r"(?i)</p>", "\\n", t)
    t = re.sub(r"(?i)<li[^>]*>", " • ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[ \\t]+\\n", "\\n", t)
    t = re.sub(r"\\n{3,}", "\\n\\n", t)
    t = re.sub(r"[ \\t]{2,}", " ", t)
    return t.strip()

def make_id(*parts):
    return hashlib.sha1("|".join(p or "" for p in parts).encode()).hexdigest()[:16]

def parse_location(raw):
    location = re.sub(r"\\s+", " ", (raw or "").strip()) or "Unknown"
    lower = location.lower()
    city = state = country = code = region = ""
    for alias, meta in CITY_COUNTRY.items():
        if alias in lower:
            city, code, country, region, state = meta
            break
    if not code:
        for alias, meta in COUNTRY_ALIAS.items():
            if re.search(rf"\\b{re.escape(alias)}\\b", lower):
                code, country, region = meta
                break
    if not city:
        first = location.split(",")[0].strip()
        if not re.search(r"remote|worldwide|anywhere", first, re.I):
            city = first
    if not country and re.search(r"\\b(remote|worldwide|anywhere|global)\\b", lower):
        country, code, region = "Remote", "REMOTE", "worldwide"
    return {"location": location, "city": city, "state": state, "country": country, "countryCode": code, "region": region}

def work_arrangement(text):
    t = (text or "").lower()
    remote = bool(re.search(r"\\bremote\\b|\\bwfh\\b|\\bdistributed\\b|\\banywhere\\b", t))
    hybrid = bool(re.search(r"\\bhybrid\\b", t))
    onsite = bool(re.search(r"\\bon-?site\\b|\\bin-?office\\b", t))
    if hybrid or (remote and onsite): return "hybrid"
    if remote: return "remote"
    if onsite: return "onsite"
    return "unknown"

def is_relevant_title(title):
    t = (title or "").lower()
    if any(bad in t for bad in TITLE_DROP): return False
    return any(k in t for k in TITLE_KEEP)

def relevance_score(title, description):
    hay = f"{title}\\n{description}".lower()
    score = 8 if is_relevant_title(title) else 0
    for kw, pts in [("c#", 12), (".net", 12), ("angular", 10), ("asp.net", 8), ("full stack", 5), ("software engineer", 4)]:
        if kw in hay: score += pts
    return score

def base_job(**kwargs):
    loc = parse_location(kwargs.get("location") or "")
    desc = strip_html(kwargs.get("description") or "")[:4000]
    title = (kwargs.get("title") or "").strip()
    company = (kwargs.get("company") or "").strip() or "Unknown"
    apply_url = kwargs.get("apply_url") or kwargs.get("job_url") or ""
    job_url = kwargs.get("job_url") or apply_url
    arr = work_arrangement(f"{title} {loc['location']} {desc}")
    exp_min, exp_max, exp_label = extract_experience(f"{title}\\n{desc}")
    techs = extract_technologies(f"{title}\\n{desc}")
    visa = classify_visa(f"{title}\\n{loc['location']}\\n{desc}", arr, loc["countryCode"])
    return {
        "id": make_id(kwargs.get("source"), kwargs.get("source_job_id"), company, title, loc["location"]),
        "sourceJobId": str(kwargs.get("source_job_id") or ""),
        "title": title, "company": company, "companyNormalized": re.sub(r"[^a-z0-9]+", "", company.lower()),
        "location": loc["location"], "city": loc["city"], "state": loc["state"],
        "country": loc["country"], "countryCode": loc["countryCode"], "region": loc["region"],
        "workArrangement": arr, "postedAt": kwargs.get("posted_at"),
        "firstDiscovered": NOW_ISO, "lastVerified": NOW_ISO, "lastChecked": NOW_ISO, "status": "open",
        "experience": exp_label or "", "experienceYearsMin": exp_min, "experienceYearsMax": exp_max,
        "technologies": techs, "visaStatus": visa.get("status", "unknown"),
        "visaEvidence": visa.get("evidence") or [], "visaLabel": visa.get("label") or "Visa sponsorship: Unknown",
        "salary": "Not specified", "salaryMin": None, "salaryMax": None, "salaryCurrency": "",
        "jobType": "unknown", "industry": extract_industry(f"{title}\\n{desc}") or "Technology",
        "source": kwargs.get("source") or "", "sources": [{"name": kwargs.get("source"), "url": job_url}],
        "applyUrl": apply_url, "jobUrl": job_url, "canonicalUrl": job_url,
        "description": desc, "excerpt": (re.sub(r"\\s+", " ", desc)[:280] + "…") if len(desc) > 280 else desc,
        "_relevance": relevance_score(title, desc),
    }

def source_greenhouse():
    out = []
    def one(board):
        data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs")
        if not data: return []
        got = []
        for item in data.get("jobs") or []:
            title = item.get("title") or ""
            if not is_relevant_title(title) and relevance_score(title, "") < 8:
                continue
            loc = (item.get("location") or {}).get("name") or ""
            jid = str(item.get("id") or "")
            url = item.get("absolute_url") or f"https://boards.greenhouse.io/{board}/jobs/{jid}"
            desc = ""
            detail = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}")
            if detail: desc = detail.get("content") or ""
            got.append(base_job(source="greenhouse", source_job_id=jid, title=title, company=board.replace("-", " ").title(),
                location=loc, apply_url=url, job_url=url, description=desc, posted_at=None))
        return got
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(one, b): b for b in GREENHOUSE_BOARDS}
        for fut in as_completed(futs):
            try:
                got = fut.result()
                out.extend(got)
                if got: log(f"  greenhouse/{futs[fut]}: {len(got)}")
            except Exception:
                log(f"  greenhouse/{futs[fut]} crashed")
    return out

def source_lever():
    out = []
    for company in LEVER_COMPANIES:
        data = fetch_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
        if not isinstance(data, list): continue
        got = []
        for item in data:
            title = item.get("text") or ""
            if not is_relevant_title(title): continue
            cats = item.get("categories") or {}
            loc = cats.get("location") or ""
            url = item.get("hostedUrl") or item.get("applyUrl") or ""
            desc = item.get("descriptionPlain") or item.get("description") or ""
            got.append(base_job(source="lever", source_job_id=item.get("id"), title=title,
                company=company.replace("-", " ").title(), location=loc, apply_url=url, job_url=url, description=desc))
        out.extend(got)
        if got: log(f"  lever/{company}: {len(got)}")
    return out

def source_public_apis():
    out = []
    data = fetch_json("https://remotive.com/api/remote-jobs?category=software-dev")
    for item in (data or {}).get("jobs") or []:
        title = item.get("title") or ""
        if not is_relevant_title(title): continue
        out.append(base_job(source="remotive", source_job_id=item.get("id"), title=title,
            company=item.get("company_name") or "", location=item.get("candidate_required_location") or "Remote",
            apply_url=item.get("url") or "", job_url=item.get("url") or "", description=item.get("description") or "",
            posted_at=item.get("publication_date")))
    log(f"  remotive: public batch")
    return out

def is_india(j):
    if (j.get("countryCode") or "").upper() == "IN": return True
    blob = f"{j.get('country') or ''} {j.get('location') or ''} {j.get('city') or ''}".lower()
    return "india" in blob or any(c in blob for c in ("bengaluru","bangalore","hyderabad","pune","chennai","mumbai","gurgaon","gurugram","noida","delhi"))

def finalize(jobs):
    scored = []
    for job in jobs:
        if job.get("_relevance", 0) < 8 and not is_relevant_title(job.get("title") or ""):
            continue
        m = score_job(job)
        job.update(m)
        job.pop("_relevance", None)
        scored.append(job)
    scored.sort(key=lambda j: (-(j.get("matchScore") or 0), j.get("postedAt") or ""))
    india = [j for j in scored if is_india(j)]
    other = [j for j in scored if not is_india(j)]
    reserve = min(INDIA_RESERVE, len(india))
    out = other[: max(0, MAX_JOBS_OUT - reserve)] + india[:reserve]
    seen = {j["id"] for j in out}
    for j in scored:
        if j["id"] not in seen:
            out.append(j); seen.add(j["id"])
        if len(out) >= MAX_JOBS_OUT: break
    out.sort(key=lambda j: (-(j.get("matchScore") or 0), j.get("postedAt") or ""))
    return out[:MAX_JOBS_OUT]

def dedupe(jobs):
    by = {}
    for job in jobs:
        key = f"{job.get('companyNormalized')}|{re.sub(r'[^a-z0-9]+','', (job.get('title') or '').lower())}|{(job.get('countryCode') or '').lower()}"
        if key not in by or (job.get("_relevance") or 0) > (by[key].get("_relevance") or 0):
            by[key] = job
    return list(by.values())

def main():
    log(f"Rolefit fetch {NOW_ISO}")
    collected = []
    for fn in (source_greenhouse, source_lever, source_public_apis):
        try: collected.extend(fn() or [])
        except Exception: log(traceback.format_exc())
    log(f"Raw collected: {len(collected)}")
    jobs = finalize(dedupe(collected))
    payload = {"updated_at": NOW_ISO, "count": len(jobs), "profile_name": PROFILE["name"], "jobs": jobs}
    for path in (ROOT / "docs" / "jobs.json", ROOT / "public" / "jobs.json"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        log(f"Wrote {path} ({len(jobs)} jobs, india={sum(1 for j in jobs if is_india(j))})")
    return 0 if jobs else 1

if __name__ == "__main__":
    sys.exit(main())
