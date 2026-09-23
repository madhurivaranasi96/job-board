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
MAX_JOBS_OUT = 500
INDIA_RESERVE = 80  # keep room for India roles even if US scores higher
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
    # Extra boards that frequently post India roles
    "rubrik", "bitwarden", "fivetran", "hackerrank", "commvault", "druva",
    "newrelic", "jumio", "pingidentity", "groww", "sezzle", "sumologic",
    "mixpanel", "karat", "linkedin", "amplitude", "salesloft", "turing",
    "vonage", "labelbox",
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
    "cred", "turing",  # India-heavy postings
]

ASHBY_ORGS = [
    "openai", "anthropic", "linear", "ramp", "vercel", "notion",
    "airtable", "rippling", "brex", "mercury", "replicate",
    "cursor", "anysphere", "perplexity", "together", "mistral",
]
