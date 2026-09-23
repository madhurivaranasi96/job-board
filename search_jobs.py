#!/usr/bin/env python3
"""
FETCH → NORMALIZE → DEDUPLICATE → RELEVANCE FILTER → VISA → MATCH → SAVE

Public ATS/job-board endpoints only. One failed source never stops the run.
No LLM. Cache previously seen jobs in pipeline/.cache.json.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pipeline.profile import PROFILE, TITLE_DROP, TITLE_KEEP  # noqa: E402
from pipeline.visa import classify_visa  # noqa: E402
from pipeline.match import extract_experience, extract_industry, extract_technologies, score_job  # noqa: E402

UA = "RolefitJobBoard/1.0 (+https://github.com/madhurivaranasi96/job-board)"
TIMEOUT = 18
MAX_JOBS_OUT = 450
CACHE_PATH = ROOT / "pipeline" / ".cache.json"
NOW = datetime.now(timezone.utc)
NOW_ISO = NOW.isoformat()

GREENHOUSE_BOARDS = [
    "stripe", "datadog", "cloudflare", "discord", "airbnb", "dropbox", "pinterest",
    "reddit", "gitlab", "mongodb", "elastic", "twilio", "hubspot", "figma", "notion",
    "airtable", "asana", "coinbase", "robinhood", "plaid", "chime", "sofi",
    "doordash", "instacart", "lyft", "gusto", "rippling", "okta", "zendesk",
    "intercom", "atlassian", "canva", "hashicorp", "grafana", "snowflake",
    "databricks", "affirm", "brex", "ramp", "mercury", "snyk", "crowdstrike",
    "1password", "cloudkitchens", "nubank", "wise", "monzo", "checkoutcom",
    "adyen", "klarna", "n26", "revolut", "starling", "dave", "marqeta",
    "toast", "square", "block", "shopify", "paypal", "visa", "mastercard",
    "capitalone", "americanexpress", "bloomberg", "jpmorganchase",
    "thoughtmachine", "temenos", "fiserv", "jackhenry", "ncr", "ncratleos",
    "dieboldnixdorf", "openai", "anthropic", "huggingface", "scaleai",
    "vercel", "linear", "remotecom", "deel", "duolingo", "grammarly",
    "elastic", "confluent", "redpanda", "dbt-labs", "hex", "omneky",
    "benchling", "c3ai", "palantirtech", "anduril", "appliedintuition",
    "cruise", "waymo", "zoox", "rivian", "tesla",
    "microsoft", "google", "amazon", "meta", "netflix", "uber",
    "salesforce", "servicenow", "workday", "intuit", "adp",
    "epam", "globant", "thoughtworks", "accenture", "capgemini",
    "infosys", "tcs", "wipro", "cognizant", "persistent",
    "freshworks", "zoho", "browserstack", "postman", "chargebee",
]

LEVER_COMPANIES = [
    "sentry", "palantir", "spotify", "wealthfront", "betterment",
    "affirm", "duolingo", "grammarly", "reddit", "twitch",
    "shopify", "netflix", "figma", "notion", "canva",
    "rippling", "deel", "remote", "oatfi", "brex",
    "ramp", "mercury", "modern-treasury", "increase", "lithic",
    "alloy", "unit", "treasuryprime", "synapse", "marqeta",
    "nubank", "truebill", "dave", "chime", "current",
    "anduril", "applied", "scale", "weightsandbiases", "huggingface",
    "replit", "vercel", "supabase", "neon", "planetscale",
]

ASHBY_ORGS = [
    "openai", "anthropic", "linear", "ramp", "vercel", "notion",
    "airtable", "rippling", "brex", "mercury", "replicate",
    "cursor", "anysphere", "perplexity", "together", "mistral",
]

# City / country helpers (subset; unknown countries still pass through)
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
    "london": ("London", "GB", "United Kingdom", "europe", ""),
    "manchester": ("Manchester", "GB", "United Kingdom", "europe", ""),
    "dublin": ("Dublin", "IE", "Ireland", "europe", ""),
    "berlin": ("Berlin", "DE", "Germany", "europe", ""),
    "munich": ("Munich", "DE", "Germany", "europe", ""),
    "hamburg": ("Hamburg", "DE", "Germany", "europe", ""),
    "frankfurt": ("Frankfurt", "DE", "Germany", "europe", ""),
    "amsterdam": ("Amsterdam", "NL", "Netherlands", "europe", ""),
    "paris": ("Paris", "FR", "France", "europe", ""),
    "zurich": ("Zurich", "CH", "Switzerland", "europe", ""),
    "geneva": ("Geneva", "CH", "Switzerland", "europe", ""),
    "stockholm": ("Stockholm", "SE", "Sweden", "europe", ""),
    "oslo": ("Oslo", "NO", "Norway", "europe", ""),
    "copenhagen": ("Copenhagen", "DK", "Denmark", "europe", ""),
    "helsinki": ("Helsinki", "FI", "Finland", "europe", ""),
    "brussels": ("Brussels", "BE", "Belgium", "europe", ""),
    "vienna": ("Vienna", "AT", "Austria", "europe", ""),
    "madrid": ("Madrid", "ES", "Spain", "europe", ""),
    "barcelona": ("Barcelona", "ES", "Spain", "europe", ""),
    "lisbon": ("Lisbon", "PT", "Portugal", "europe", ""),
    "warsaw": ("Warsaw", "PL", "Poland", "europe", ""),
    "prague": ("Prague", "CZ", "Czech Republic", "europe", ""),
    "sydney": ("Sydney", "AU", "Australia", "asia-pacific", ""),
    "melbourne": ("Melbourne", "AU", "Australia", "asia-pacific", ""),
    "auckland": ("Auckland", "NZ", "New Zealand", "asia-pacific", ""),
    "singapore": ("Singapore", "SG", "Singapore", "asia-pacific", ""),
    "tokyo": ("Tokyo", "JP", "Japan", "asia-pacific", ""),
    "seoul": ("Seoul", "KR", "South Korea", "asia-pacific", ""),
    "dubai": ("Dubai", "AE", "United Arab Emirates", "middle-east", ""),
    "doha": ("Doha", "QA", "Qatar", "middle-east", ""),
    "riyadh": ("Riyadh", "SA", "Saudi Arabia", "middle-east", ""),
    "new york": ("New York", "US", "United States", "north-america", "NY"),
    "san francisco": ("San Francisco", "US", "United States", "north-america", "CA"),
    "seattle": ("Seattle", "US", "United States", "north-america", "WA"),
    "austin": ("Austin", "US", "United States", "north-america", "TX"),
    "boston": ("Boston", "US", "United States", "north-america", "MA"),
    "chicago": ("Chicago", "US", "United States", "north-america", "IL"),
    "denver": ("Denver", "US", "United States", "north-america", "CO"),
    "atlanta": ("Atlanta", "US", "United States", "north-america", "GA"),
    "toronto": ("Toronto", "CA", "Canada", "north-america", "ON"),
    "vancouver": ("Vancouver", "CA", "Canada", "north-america", "BC"),
    "montreal": ("Montreal", "CA", "Canada", "north-america", "QC"),
}

COUNTRY_ALIAS = {
    "usa": ("US", "United States", "north-america"),
    "us": ("US", "United States", "north-america"),
    "united states": ("US", "United States", "north-america"),
    "united states of america": ("US", "United States", "north-america"),
    "canada": ("CA", "Canada", "north-america"),
    "uk": ("GB", "United Kingdom", "europe"),
    "united kingdom": ("GB", "United Kingdom", "europe"),
    "great britain": ("GB", "United Kingdom", "europe"),
    "england": ("GB", "United Kingdom", "europe"),
    "ireland": ("IE", "Ireland", "europe"),
    "germany": ("DE", "Germany", "europe"),
    "deutschland": ("DE", "Germany", "europe"),
    "netherlands": ("NL", "Netherlands", "europe"),
    "holland": ("NL", "Netherlands", "europe"),
    "france": ("FR", "France", "europe"),
    "switzerland": ("CH", "Switzerland", "europe"),
    "sweden": ("SE", "Sweden", "europe"),
    "norway": ("NO", "Norway", "europe"),
    "denmark": ("DK", "Denmark", "europe"),
    "finland": ("FI", "Finland", "europe"),
    "belgium": ("BE", "Belgium", "europe"),
    "austria": ("AT", "Austria", "europe"),
    "spain": ("ES", "Spain", "europe"),
    "portugal": ("PT", "Portugal", "europe"),
    "poland": ("PL", "Poland", "europe"),
    "czech republic": ("CZ", "Czech Republic", "europe"),
    "czechia": ("CZ", "Czech Republic", "europe"),
    "italy": ("IT", "Italy", "europe"),
    "australia": ("AU", "Australia", "asia-pacific"),
    "new zealand": ("NZ", "New Zealand", "asia-pacific"),
    "singapore": ("SG", "Singapore", "asia-pacific"),
    "japan": ("JP", "Japan", "asia-pacific"),
    "south korea": ("KR", "South Korea", "asia-pacific"),
    "korea": ("KR", "South Korea", "asia-pacific"),
    "india": ("IN", "India", "south-asia"),
    "uae": ("AE", "United Arab Emirates", "middle-east"),
    "united arab emirates": ("AE", "United Arab Emirates", "middle-east"),
    "saudi arabia": ("SA", "Saudi Arabia", "middle-east"),
    "qatar": ("QA", "Qatar", "middle-east"),
    "remote": ("REMOTE", "Remote", "worldwide"),
    "worldwide": ("REMOTE", "Remote", "worldwide"),
}


def log(msg: str) -> None:
    print(msg, flush=True)


def fetch_json(url: str, headers: dict | None = None):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = Request(url, headers=h)
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8", "replace"))
    except HTTPError as e:
        if e.code in (404, 403, 401, 410, 429):
            return None
        log(f"  HTTP {e.code} {url[:80]}")
        return None
    except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
        log(f"  fail {url[:72]} ({e.__class__.__name__})")
        return None


def strip_html(text: str) -> str:
    if not text:
        return ""
    t = html.unescape(html.unescape(text))
    t = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</p>", "\n", t)
    t = re.sub(r"(?i)<li[^>]*>", " • ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def excerpt(text: str, n: int = 280) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t[: n - 1] + "…" if len(t) > n else t


def normalize_company(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def make_id(*parts: str) -> str:
    raw = "|".join(p or "" for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def parse_location(raw: str) -> dict:
    location = re.sub(r"\s+", " ", (raw or "").strip()) or "Unknown"
    lower = location.lower()
    city = state = country = code = region = ""

    for alias, meta in CITY_COUNTRY.items():
        if alias in lower:
            city, code, country, region, state = meta
            break
    if not code:
        for alias, meta in COUNTRY_ALIAS.items():
            if re.search(rf"\b{re.escape(alias)}\b", lower):
                code, country, region = meta
                break
    if not code and re.search(
        r"\b(AL|AK|AZ|AR|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VA|VT|WA|WI|WV)\b",
        location,
    ):
        # IN is India code too; only treat as US if it looks like a state list with a US city comma
        if re.search(r",\s*(CA|NY|TX|WA|MA|IL|CO|GA|FL|PA|VA|NC|OR|NJ|AZ)\b", location):
            code, country, region = "US", "United States", "north-america"
    if not city:
        first = location.split(",")[0].strip()
        if not re.search(r"remote|worldwide|anywhere", first, re.I):
            city = first
    if not country and re.search(r"\b(remote|worldwide|anywhere|global)\b", lower):
        country, code, region = "Remote", "REMOTE", "worldwide"
    return {
        "location": location,
        "city": city,
        "state": state,
        "country": country,
        "countryCode": code,
        "region": region,
    }


def work_arrangement(text: str) -> str:
    t = (text or "").lower()
    remote = bool(re.search(r"\bremote\b|\bwork from home\b|\bwfh\b|\bdistributed\b|\banywhere\b", t))
    hybrid = bool(re.search(r"\bhybrid\b", t))
    onsite = bool(re.search(r"\bon-?site\b|\bin-?office\b|\bin office\b", t))
    if hybrid or (remote and onsite):
        return "hybrid"
    if remote:
        return "remote"
    if onsite:
        return "onsite"
    return "unknown"


def job_type_of(text: str) -> str:
    t = (text or "").lower()
    if "contract" in t or "contractor" in t:
        return "contract"
    if "temporary" in t or "temp " in t:
        return "temporary"
    if "permanent" in t:
        return "permanent"
    if "full-time" in t or "full time" in t:
        return "full-time"
    return "unknown"


def parse_salary(text: str) -> tuple[str, int | None, int | None, str]:
    t = text or ""
    currency = ""
    if "$" in t or "usd" in t.lower():
        currency = "USD"
    elif "£" in t or "gbp" in t.lower():
        currency = "GBP"
    elif "€" in t or "eur" in t.lower():
        currency = "EUR"
    elif "₹" in t or "inr" in t.lower():
        currency = "INR"
    elif "cad" in t.lower():
        currency = "CAD"
    elif "aud" in t.lower():
        currency = "AUD"
    m = re.search(
        r"([\$£€₹]|USD|GBP|EUR|INR|CAD|AUD)?\s*([0-9]{2,3}(?:,[0-9]{3})|[0-9]{2,3})[kK]?\s*[-–to]+\s*([\$£€₹]|USD|GBP|EUR|INR|CAD|AUD)?\s*([0-9]{2,3}(?:,[0-9]{3})|[0-9]{2,3})[kK]?",
        t,
    )
    if m:
        def num(s: str) -> int:
            s = s.replace(",", "")
            v = int(s)
            return v * 1000 if v < 1000 else v
        lo, hi = num(m.group(2)), num(m.group(4))
        label = f"{m.group(0).strip()}"
        return excerpt(label, 80), lo, hi, currency
    return ("Not specified", None, None, currency)


def is_relevant_title(title: str) -> bool:
    t = (title or "").lower()
    if any(bad in t for bad in TITLE_DROP):
        return False
    return any(k in t for k in TITLE_KEEP)


def relevance_score(title: str, description: str) -> int:
    hay = f"{title}\n{description}".lower()
    score = 0
    if is_relevant_title(title):
        score += 8
    for kw, pts in [
        ("c#", 12), ("csharp", 12), (".net", 12), ("dotnet", 10),
        ("angular", 10), ("asp.net", 8), ("web api", 6),
        ("typescript", 4), ("javascript", 3), ("full stack", 5),
        ("fullstack", 5), ("software engineer", 4), ("agentic", 8),
        ("llm", 5), ("banking", 4), ("atm", 5), ("fintech", 3),
    ]:
        if kw in hay:
            score += pts
    return score


def iso_date(value) -> str | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        # seconds or ms
        ts = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value)
    m = re.match(r"(\d{4}-\d{2}-\d{2}(?:[tT ]\d{2}:\d{2}:\d{2})?)", s)
    if m:
        raw = m.group(1).replace(" ", "T")
        if len(raw) == 10:
            raw += "T00:00:00"
        try:
            return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            return raw + "+00:00"
    return None


def base_job(**kwargs) -> dict:
    loc = parse_location(kwargs.get("location") or "")
    desc = strip_html(kwargs.get("description") or "")[:4000]
    title = (kwargs.get("title") or "").strip()
    company = (kwargs.get("company") or "").strip() or "Unknown"
    apply_url = kwargs.get("apply_url") or kwargs.get("job_url") or ""
    job_url = kwargs.get("job_url") or apply_url
    arr = work_arrangement(f"{title} {loc['location']} {desc}")
    exp_min, exp_max, exp_label = extract_experience(f"{title}\n{desc}")
    techs = extract_technologies(f"{title}\n{desc}")
    visa = classify_visa(f"{title}\n{loc['location']}\n{desc}", arr, loc["countryCode"])
    salary_label, smin, smax, scur = parse_salary(desc)
    if kwargs.get("salary") and kwargs["salary"] not in ("", "Not specified"):
        salary_label = str(kwargs["salary"])
        a, b, c, d = parse_salary(salary_label)
        smin, smax, scur = b or smin, c or smax, d or scur
    posted = iso_date(kwargs.get("posted"))
    source = kwargs.get("source") or "unknown"
    sid = str(kwargs.get("source_id") or "")
    jid = make_id(normalize_company(company), title.lower(), loc["location"].lower(), sid or apply_url)
    job = {
        "id": jid,
        "sourceJobId": sid,
        "title": title,
        "company": company,
        "companyNormalized": normalize_company(company),
        **loc,
        "workArrangement": arr,
        "postedAt": posted,
        "firstDiscovered": NOW_ISO,
        "lastVerified": NOW_ISO,
        "lastChecked": NOW_ISO,
        "status": "open",
        "experience": exp_label,
        "experienceYearsMin": exp_min,
        "experienceYearsMax": exp_max,
        "technologies": techs,
        "visaStatus": visa["status"],
        "visaEvidence": visa["evidence"],
        "visaLabel": visa["label"],
        "salary": salary_label or "Not specified",
        "salaryMin": smin,
        "salaryMax": smax,
        "salaryCurrency": scur,
        "jobType": job_type_of(f"{title} {desc}"),
        "industry": extract_industry(f"{title}\n{company}\n{desc}"),
        "source": source,
        "sources": [{"name": source, "url": job_url}],
        "applyUrl": apply_url,
        "jobUrl": job_url,
        "canonicalUrl": job_url,
        "description": desc,
        "excerpt": excerpt(desc),
        "matchScore": 0,
        "matchReasons": [],
        "missingRequirements": [],
        "concerns": [],
        "_relevance": relevance_score(title, desc),
    }
    return job


# --------------- sources ---------------

def source_greenhouse() -> list[dict]:
    jobs: list[dict] = []

    def one(board: str) -> list[dict]:
        data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs")
        if not data or not isinstance(data, dict):
            return []
        out = []
        listings = data.get("jobs") or []
        picked = []
        for item in listings:
            title = item.get("title") or ""
            if not is_relevant_title(title):
                continue
            picked.append(item)
        # fetch details for the most relevant titles first
        picked = picked[:25]
        for item in picked:
            jid = item.get("id")
            detail = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}") or item
            loc = ""
            if isinstance(detail.get("location"), dict):
                loc = detail["location"].get("name") or ""
            elif isinstance(item.get("location"), dict):
                loc = item["location"].get("name") or ""
            company = detail.get("company_name") or board.replace("-", " ").title()
            content = detail.get("content") or ""
            url = detail.get("absolute_url") or item.get("absolute_url") or ""
            out.append(
                base_job(
                    title=detail.get("title") or title,
                    company=company,
                    location=loc,
                    description=content,
                    apply_url=url,
                    job_url=url,
                    posted=detail.get("first_published") or detail.get("updated_at"),
                    source="greenhouse",
                    source_id=str(jid or ""),
                )
            )
        return out

    log(f"Greenhouse: {len(GREENHOUSE_BOARDS)} boards")
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(one, b): b for b in GREENHOUSE_BOARDS}
        for fut in as_completed(futs):
            board = futs[fut]
            try:
                got = fut.result()
                if got:
                    log(f"  greenhouse/{board}: {len(got)}")
                    jobs.extend(got)
            except Exception:
                log(f"  greenhouse/{board} crashed")
    return jobs


def source_lever() -> list[dict]:
    jobs: list[dict] = []

    def one(company: str) -> list[dict]:
        data = fetch_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
        if not data or not isinstance(data, list):
            return []
        out = []
        for item in data:
            title = item.get("text") or item.get("title") or ""
            if not is_relevant_title(title):
                continue
            cats = item.get("categories") or {}
            loc = cats.get("location") or item.get("country") or ""
            desc = item.get("descriptionPlain") or item.get("description") or ""
            lists = item.get("lists") or []
            extra = "\n".join(f"{x.get('text','')}\n{x.get('content','')}" for x in lists)
            url = item.get("hostedUrl") or item.get("applyUrl") or ""
            apply_url = item.get("applyUrl") or url
            out.append(
                base_job(
                    title=title,
                    company=item.get("categories", {}).get("commitment") and company.replace("-", " ").title() or company.replace("-", " ").title(),
                    location=loc,
                    description=f"{desc}\n{extra}",
                    apply_url=apply_url,
                    job_url=url,
                    posted=item.get("createdAt"),
                    source="lever",
                    source_id=str(item.get("id") or ""),
                    salary=(item.get("salaryRange") and json.dumps(item.get("salaryRange"))) or "",
                )
            )
            if len(out) >= 25:
                break
        return out

    log(f"Lever: {len(LEVER_COMPANIES)} companies")
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(one, c): c for c in LEVER_COMPANIES}
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                got = fut.result()
                if got:
                    log(f"  lever/{c}: {len(got)}")
                    jobs.extend(got)
            except Exception:
                log(f"  lever/{c} crashed")
    return jobs


def source_ashby() -> list[dict]:
    jobs: list[dict] = []

    def one(org: str) -> list[dict]:
        data = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{org}")
        if not data:
            return []
        listings = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(listings, list):
            return []
        out = []
        for item in listings:
            title = item.get("title") or ""
            if not is_relevant_title(title):
                continue
            loc = item.get("location") or ""
            if isinstance(loc, dict):
                loc = loc.get("locationName") or loc.get("name") or ""
            url = item.get("jobUrl") or item.get("applyUrl") or ""
            desc = item.get("descriptionHtml") or item.get("descriptionPlain") or item.get("description") or ""
            out.append(
                base_job(
                    title=title,
                    company=item.get("departmentName") and org.replace("-", " ").title() or org.replace("-", " ").title(),
                    location=str(loc),
                    description=desc,
                    apply_url=item.get("applyUrl") or url,
                    job_url=url,
                    posted=item.get("publishedAt") or item.get("updatedAt"),
                    source="ashby",
                    source_id=str(item.get("id") or ""),
                )
            )
            if len(out) >= 25:
                break
        return out

    log(f"Ashby: {len(ASHBY_ORGS)} orgs")
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(one, o): o for o in ASHBY_ORGS}
        for fut in as_completed(futs):
            o = futs[fut]
            try:
                got = fut.result()
                if got:
                    log(f"  ashby/{o}: {len(got)}")
                    jobs.extend(got)
            except Exception:
                log(f"  ashby/{o} crashed")
    return jobs


def source_remotive() -> list[dict]:
    log("Remotive")
    data = fetch_json("https://remotive.com/api/remote-jobs?category=software-dev")
    if not data:
        return []
    out = []
    for item in data.get("jobs") or []:
        title = item.get("title") or ""
        if not is_relevant_title(title) and relevance_score(title, item.get("description") or "") < 8:
            continue
        out.append(
            base_job(
                title=title,
                company=item.get("company_name") or "",
                location=item.get("candidate_required_location") or "Remote",
                description=item.get("description") or "",
                apply_url=item.get("url") or "",
                job_url=item.get("url") or "",
                posted=item.get("publication_date"),
                source="remotive",
                source_id=str(item.get("id") or ""),
                salary=item.get("salary") or "",
            )
        )
    log(f"  remotive: {len(out)}")
    return out


def source_arbeitnow() -> list[dict]:
    log("Arbeitnow")
    data = fetch_json("https://www.arbeitnow.com/api/job-board-api")
    if not data:
        return []
    listings = data.get("data") if isinstance(data, dict) else data
    out = []
    for item in listings or []:
        title = item.get("title") or ""
        if not is_relevant_title(title):
            continue
        tags = " ".join(item.get("tags") or [])
        loc = item.get("location") or ""
        remote = item.get("remote")
        if remote:
            loc = (loc + " Remote").strip()
        out.append(
            base_job(
                title=title,
                company=item.get("company_name") or "",
                location=loc,
                description=(item.get("description") or "") + "\n" + tags,
                apply_url=item.get("url") or "",
                job_url=item.get("url") or "",
                posted=item.get("created_at"),
                source="arbeitnow",
                source_id=item.get("slug") or "",
            )
        )
        if len(out) >= 120:
            break
    log(f"  arbeitnow: {len(out)}")
    return out


def source_jobicy() -> list[dict]:
    log("Jobicy")
    out = []
    for tag in ("javascript", "software-engineering", "python"):
        data = fetch_json(f"https://jobicy.com/api/v2/remote-jobs?count=50&tag={tag}")
        if not data:
            continue
        for item in data.get("jobs") or []:
            title = item.get("jobTitle") or item.get("title") or ""
            if not is_relevant_title(title) and relevance_score(title, item.get("jobDescription") or "") < 8:
                continue
            out.append(
                base_job(
                    title=title,
                    company=item.get("companyName") or "",
                    location=item.get("jobGeo") or "Remote",
                    description=item.get("jobDescription") or item.get("jobExcerpt") or "",
                    apply_url=item.get("url") or "",
                    job_url=item.get("url") or "",
                    posted=item.get("pubDate") or item.get("jobPubDate"),
                    source="jobicy",
                    source_id=str(item.get("id") or ""),
                    salary=item.get("salary") or item.get("annualSalaryMin") and f"{item.get('annualSalaryMin')}-{item.get('annualSalaryMax')}" or "",
                )
            )
    log(f"  jobicy: {len(out)}")
    return out


def source_remoteok() -> list[dict]:
    log("RemoteOK")
    data = fetch_json("https://remoteok.com/api")
    if not data or not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict) or not item.get("id") or not item.get("position"):
            continue
        title = item.get("position") or item.get("title") or ""
        if not is_relevant_title(title) and relevance_score(title, item.get("description") or "") < 8:
            continue
        loc = item.get("location") or "Remote"
        tags = " ".join(item.get("tags") or [])
        out.append(
            base_job(
                title=title,
                company=item.get("company") or "",
                location=loc,
                description=(item.get("description") or "") + "\n" + tags,
                apply_url=item.get("url") or item.get("apply_url") or "",
                job_url=item.get("url") or "",
                posted=item.get("date") or item.get("epoch"),
                source="remoteok",
                source_id=str(item.get("id") or ""),
                salary=item.get("salary") or "",
            )
        )
        if len(out) >= 80:
            break
    log(f"  remoteok: {len(out)}")
    return out


def source_himalayas() -> list[dict]:
    log("Himalayas")
    data = fetch_json("https://himalayas.app/jobs/api?limit=100")
    if not data:
        return []
    listings = data.get("jobs") if isinstance(data, dict) else data
    out = []
    for item in listings or []:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or ""
        if not is_relevant_title(title):
            continue
        loc = item.get("location") or item.get("countries") or "Remote"
        if isinstance(loc, list):
            loc = ", ".join(str(x) for x in loc)
        desc = item.get("description") or item.get("excerpt") or ""
        url = item.get("applicationLink") or item.get("url") or item.get("guid") or ""
        out.append(
            base_job(
                title=title,
                company=item.get("companyName") or item.get("company") or "",
                location=str(loc),
                description=desc,
                apply_url=url,
                job_url=url,
                posted=item.get("pubDate") or item.get("publishedAt"),
                source="himalayas",
                source_id=str(item.get("id") or item.get("guid") or ""),
            )
        )
    log(f"  himalayas: {len(out)}")
    return out


def source_themuse() -> list[dict]:
    log("The Muse")
    out = []
    for page in range(0, 3):
        data = fetch_json(
            f"https://www.themuse.com/api/public/jobs?category=Software%20Engineering&page={page}&descending=true"
        )
        if not data:
            break
        for item in data.get("results") or []:
            title = item.get("name") or ""
            if not is_relevant_title(title):
                continue
            locs = item.get("locations") or []
            loc = ", ".join(x.get("name") or "" for x in locs) or "Unknown"
            company = (item.get("company") or {}).get("name") or ""
            refs = item.get("refs") or {}
            url = refs.get("landing_page") or ""
            out.append(
                base_job(
                    title=title,
                    company=company,
                    location=loc,
                    description=item.get("contents") or "",
                    apply_url=url,
                    job_url=url,
                    posted=item.get("publication_date"),
                    source="themuse",
                    source_id=str(item.get("id") or ""),
                )
            )
    log(f"  themuse: {len(out)}")
    return out


def dedupe(jobs: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for job in jobs:
        url_key = ""
        try:
            p = urlparse(job.get("canonicalUrl") or job.get("jobUrl") or "")
            url_key = (p.netloc + p.path).lower().rstrip("/")
        except Exception:
            url_key = ""
        key = job.get("sourceJobId") and f"{job['source']}:{job['sourceJobId']}"
        title_key = f"{job.get('companyNormalized')}|{re.sub(r'[^a-z0-9]+','', (job.get('title') or '').lower())}|{(job.get('countryCode') or job.get('location') or '').lower()}"
        chosen = key or url_key or title_key
        # also merge if title_key already exists
        existing = by_key.get(chosen) or by_key.get(title_key)
        if existing:
            src = {"name": job.get("source"), "url": job.get("jobUrl")}
            if src not in existing.get("sources", []):
                existing.setdefault("sources", []).append(src)
            if (job.get("_relevance") or 0) > (existing.get("_relevance") or 0):
                job["sources"] = existing.get("sources", job.get("sources"))
                job["firstDiscovered"] = existing.get("firstDiscovered") or job["firstDiscovered"]
                by_key[chosen] = job
                by_key[title_key] = job
            continue
        by_key[chosen] = job
        by_key[title_key] = job
    # unique by id
    uniq = {}
    for j in by_key.values():
        uniq[j["id"]] = j
    return list(uniq.values())


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"jobs": {}}
    return {"jobs": {}}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def apply_cache(jobs: list[dict], cache: dict) -> list[dict]:
    stored = cache.setdefault("jobs", {})
    out = []
    for job in jobs:
        prev = stored.get(job["id"])
        if prev:
            job["firstDiscovered"] = prev.get("firstDiscovered") or job["firstDiscovered"]
            # if description unchanged, keep previous visa/match? still recompute — cheap
        stored[job["id"]] = {
            "firstDiscovered": job["firstDiscovered"],
            "canonicalUrl": job.get("canonicalUrl"),
            "lastChecked": NOW_ISO,
        }
        out.append(job)
    # mark missing as unknown/closed if older than 21 days and not seen
    return out


def finalize(jobs: list[dict]) -> list[dict]:
    scored = []
    for job in jobs:
        if job.get("_relevance", 0) < 8 and not is_relevant_title(job.get("title") or ""):
            continue
        m = score_job(job)
        job.update(m)
        job.pop("_relevance", None)
        scored.append(job)
    scored.sort(key=lambda j: (-(j.get("matchScore") or 0), j.get("postedAt") or ""))
    return scored[:MAX_JOBS_OUT]


def write_outputs(jobs: list[dict]) -> None:
    payload = {
        "updated_at": NOW_ISO,
        "count": len(jobs),
        "profile_name": PROFILE["name"],
        "jobs": jobs,
    }
    targets = [
        ROOT / "public" / "jobs.json",
        ROOT / "docs" / "jobs.json",
    ]
    # GitHub Pages clone lives separately when run in CI from repo root
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        log(f"Wrote {path} ({len(jobs)} jobs)")


def main() -> int:
    log(f"Rolefit fetch {NOW_ISO}")
    sources = [
        source_greenhouse,
        source_lever,
        source_ashby,
        source_remotive,
        source_arbeitnow,
        source_jobicy,
        source_remoteok,
        source_himalayas,
        source_themuse,
    ]
    collected: list[dict] = []
    for fn in sources:
        try:
            collected.extend(fn() or [])
        except Exception:
            log(f"Source {fn.__name__} failed:\n{traceback.format_exc()}")
    log(f"Raw collected: {len(collected)}")
    cache = load_cache()
    jobs = apply_cache(dedupe(collected), cache)
    jobs = finalize(jobs)
    save_cache(cache)
    write_outputs(jobs)
    visa_counts: dict[str, int] = {}
    for j in jobs:
        visa_counts[j["visaStatus"]] = visa_counts.get(j["visaStatus"], 0) + 1
    log(f"Final {len(jobs)} jobs | visa {visa_counts}")
    return 0 if jobs else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
