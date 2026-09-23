# Software Jobs Board

Public web application to browse, search, and filter recent software engineering jobs (.NET, Angular, Full-Stack, AI, and related roles).

**Repository → GitHub Pages → Public HTTPS URL**

## Live Website

After enabling GitHub Pages (Settings → Pages → Source: Deploy from branch `main` / folder `/docs`):

**https://madhurivaranasi96.github.io/job-board/**

## Features

- Browse latest jobs (auto-refreshed daily)
- Full-text search
- Filters: Remote, Visa/Sponsorship, Country
- Sort by date / company / title
- Job detail modal with description and original Apply URL
- Mark jobs as Applied / Opened / Skipped (stored in browser under your display name)
- “My Applied” view retains marks even if the job leaves the latest 7-day feed

No login is required to browse or search. A local display name is only needed when marking Applied status.

## How jobs are updated

GitHub Actions runs `search_jobs.py` on a schedule (and on manual trigger).

It:

1. Pulls recent postings from preferred ATS sources
2. Filters to software / .NET / Angular / AI–related titles
3. Writes `docs/jobs.json`
4. Commits the file so the live site updates automatically

## Manual trigger

Actions → **Update Job List** → Run workflow

## Local development

```bash
# Serve the site
cd docs && python -m http.server 8080
# Open http://localhost:8080
```

To regenerate jobs (requires network + `pip install -r requirements.txt`):

```bash
python search_jobs.py
```

## Notes

- Visa detection is text-based only; always verify on the employer site.
- Applied status is stored in the browser (`localStorage`). Clearing site data clears marks.
- For multi-device sync you would need a backend (e.g. Supabase); this version stays free and static.

## Credits

Inspired by [saipisupati-appsec/Manual_apply](https://github.com/saipisupati-appsec/Manual_apply).
