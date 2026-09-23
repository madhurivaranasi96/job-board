# Rolefit — personal job search

Public job-search board for **Madhuri Varanasi**. It scores live software roles against a resume-derived profile, flags visa / sponsorship language when the posting actually says so, and tracks applications in the browser.

**Live site:** https://madhurivaranasi96.github.io/job-board/

## What it does

- Pulls recent roles from public ATS endpoints (Greenhouse, Lever, Ashby) and public job APIs (Remotive, Arbeitnow, Jobicy, RemoteOK, Himalayas, The Muse)
- Deduplicates by company + title + location + job id / URL
- Classifies visa status from the posting text only (`Sponsorship Available`, `Likely`, `Unknown`, `No Sponsorship`, `Existing authorization required`, `Not applicable / remote`)
- Scores each role against a centralized profile (skills, title, seniority, domain, location, sponsorship)
- Filters: country, region (including Remote USA / Europe / UK / Canada / APAC / India / anywhere), city, arrangement, visa, experience, title, technology, industry, job type, posted date, salary
- Application tracker (Saved → Offer) in `localStorage`

The public site never includes a resume file, phone number, or email.

## How jobs update

GitHub Actions runs `search_jobs.py` daily (09:00 IST) and on manual dispatch:

1. FETCH public sources (one failed source does not stop the run)
2. NORMALIZE locations, dates, salary, technologies
3. DEDUPLICATE
4. RELEVANCE FILTER (software / .NET / Angular / full-stack / AI-adjacent titles)
5. VISA DETECTION (regex / keywords; never fabricated)
6. PROFILE MATCHING (deterministic weights)
7. SAVE `docs/jobs.json`
8. GitHub Pages serves `docs/`

Manual run: **Actions → Update Job List → Run workflow**

## Local

```bash
python search_jobs.py
cd docs && python -m http.server 8080
```

## Visa detection

Status is assigned only from evidence in the posting. If nothing matches, the UI shows **Visa sponsorship: Unknown** and quotes nothing. Apply always opens the original employer URL.

## Notes

- Visa / salary / experience fields are only as good as the public posting.
- Marketplace listings (e.g. agencies that name many stacks) can inflate technology overlap.
- Tracking is per-browser. Clearing site data clears marks.
