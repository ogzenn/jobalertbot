# Job Alert Bot 🚨

Automatically posts fresh Data Analyst / Python / SQL / Data Scientist / Internship
job listings to a Discord channel, pulling from 5 free public job APIs:

- **RemoteOK** — remote tech jobs
- **WeWorkRemotely** — remote programming/data RSS feeds
- **Arbeitnow** — aggregates jobs from Greenhouse, SmartRecruiters, and others (EU/remote heavy)
- **Jobicy** — remote jobs, filtered to data-science and dev industries
- **Himalayas** — remote jobs, searched per keyword

This is a wide net across free, no-auth-required sources — not literally every job
on the internet (LinkedIn/Naukri/Indeed don't offer public APIs and scraping them
breaks their terms), but it covers the major legitimate remote job boards.

Runs for free every 30 minutes via GitHub Actions — no server, no hosting cost.

## How it works

1. `job_alert_bot.py` fetches jobs from all 5 sources above
2. Filters them by keyword (see `KEYWORDS` in the script)
3. Deduplicates jobs that appear on multiple boards (same title + company)
4. Checks `seen_jobs.json` to skip anything already posted
5. Posts new matches to your Discord channel via a webhook
6. Saves the updated seen list back to the repo

GitHub Actions handles the scheduling — the workflow in
`.github/workflows/job-alert.yml` runs the script every 30 minutes automatically.

## Setup

### 1. Create a Discord webhook

- In your Discord server, go to the target channel → gear icon → **Integrations** → **Webhooks** → **New Webhook**
- Copy the webhook URL

### 2. Add your webhook as a GitHub Secret

- In your GitHub repo: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
- Name: `DISCORD_WEBHOOK_URL`
- Value: paste your webhook URL
- Save

### 3. Test it manually

- Go to the **Actions** tab in your repo
- Click **Job Alert Bot** workflow → **Run workflow** → **Run workflow**
- Check the run logs, then check your Discord channel

If it works, you're done — it will now run automatically every 30 minutes forever, for free.

## Customizing

- **Change keywords**: edit the `KEYWORDS` list in `job_alert_bot.py`
- **Change frequency**: edit the cron schedule in `.github/workflows/job-alert.yml`
  (`*/30 * * * *` = every 30 min; `*/15 * * * *` = every 15 min, etc.)
- **Add more sources**: add a new fetcher function following the pattern of
  `fetch_remoteok_jobs()` or `fetch_arbeitnow_jobs()`, then include it in `main()`
- **Fintech companies (JPMorgan, Barclays, HSBC, Amex)**: these run on Workday, which
  doesn't expose a simple public API like Greenhouse does. They were intentionally left
  out to keep this bot stable — Workday's endpoints are per-tenant and less predictable.
  If you want to add one later, look for a `*.wd*.myworkdayjobs.com` URL on their careers
  page and I can help wire up a fetcher for it.

## Notes

- GitHub Actions free tier gives 2,000 minutes/month for private repos —
  this script runs in seconds, so even every-15-min scheduling won't come close to the limit.
  Public repos get unlimited minutes.
- Scheduled workflows can be delayed a few minutes during GitHub's high-load periods — this is normal and not a bug.
- RemoteOK's API requires attribution and direct links to their listings, which this bot already does (title + direct URL, no redirect).
