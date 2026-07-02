"""
Job Alert Bot
Fetches fresh job postings from RemoteOK + WeWorkRemotely,
filters for Data Analyst / Python / SQL / Data Scientist / Internship roles,
and posts new ones to a Discord channel via webhook.

Designed to run on a schedule (e.g. GitHub Actions cron every 30 min).
State (already-posted job IDs) is kept in seen_jobs.json so we never repost.
"""

import os
import json
import time
import requests
import feedparser
from pathlib import Path

# ---------- CONFIG ----------

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

KEYWORDS = [
    "data analyst",
    "data scientist",
    "data science",
    "python developer",
    "python dev",
    "sql developer",
    "sql dev",
    "intern",
    "internship",
]

SEEN_FILE = Path(__file__).parent / "seen_jobs.json"

REMOTEOK_API = "https://remoteok.com/api"

WWR_FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-data-jobs.rss",
]

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"

# Jobicy: one call per relevant industry tag keeps results focused
JOBICY_QUERIES = [
    "https://jobicy.com/api/v2/remote-jobs?count=50&industry=data-science",
    "https://jobicy.com/api/v2/remote-jobs?count=50&industry=dev",
]

# Himalayas: one search call per keyword (search endpoint takes a single query)
HIMALAYAS_SEARCH_TERMS = [
    "data analyst",
    "data scientist",
    "python developer",
    "sql developer",
]

REQUEST_HEADERS = {
    # RemoteOK blocks requests without a normal-looking User-Agent
    "User-Agent": "Mozilla/5.0 (compatible; JobAlertBot/1.0; +https://github.com/)"
}

# ---------- STATE ----------

def load_seen():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen_ids):
    # keep the file from growing forever - cap at last 2000 ids
    trimmed = list(seen_ids)[-2000:]
    SEEN_FILE.write_text(json.dumps(trimmed))


# ---------- FETCHERS ----------

def fetch_remoteok_jobs():
    """Returns list of dicts: id, title, company, url, description, tags"""
    try:
        resp = requests.get(REMOTEOK_API, headers=REQUEST_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[RemoteOK] fetch failed: {e}")
        return []

    jobs = []
    for item in data:
        if not isinstance(item, dict) or "id" not in item:
            continue  # first element is often a metadata blob, skip it
        jobs.append({
            "id": f"remoteok_{item.get('id')}",
            "title": item.get("position", "Untitled role"),
            "company": item.get("company", "Unknown company"),
            "url": item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id')}",
            "description": (item.get("description") or "")[:500],
            "tags": " ".join(item.get("tags", [])),
            "source": "RemoteOK",
        })
    return jobs


def fetch_wwr_jobs():
    """Parses WeWorkRemotely RSS feeds"""
    jobs = []
    for feed_url in WWR_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[WWR] fetch failed for {feed_url}: {e}")
            continue

        for entry in feed.entries:
            job_id = entry.get("id") or entry.get("link")
            jobs.append({
                "id": f"wwr_{job_id}",
                "title": entry.get("title", "Untitled role"),
                "company": "",  # WWR titles are usually "Company: Role"
                "url": entry.get("link", ""),
                "description": (entry.get("summary") or "")[:500],
                "tags": "",
                "source": "WeWorkRemotely",
            })
    return jobs


def fetch_arbeitnow_jobs():
    """Arbeitnow aggregates jobs from Greenhouse, SmartRecruiters, and others - EU/remote focused."""
    try:
        resp = requests.get(ARBEITNOW_API, headers=REQUEST_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Arbeitnow] fetch failed: {e}")
        return []

    jobs = []
    for item in data.get("data", []):
        slug = item.get("slug", "")
        jobs.append({
            "id": f"arbeitnow_{slug}",
            "title": item.get("title", "Untitled role"),
            "company": item.get("company_name", "Unknown company"),
            "url": item.get("url", ""),
            "description": (item.get("description") or "")[:500],
            "tags": " ".join(item.get("tags", [])),
            "source": "Arbeitnow",
        })
    return jobs


def fetch_jobicy_jobs():
    """Jobicy: remote jobs, queried per industry tag."""
    jobs = []
    for feed_url in JOBICY_QUERIES:
        try:
            resp = requests.get(feed_url, headers=REQUEST_HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[Jobicy] fetch failed for {feed_url}: {e}")
            continue

        for item in data.get("jobs", []):
            jobs.append({
                "id": f"jobicy_{item.get('id')}",
                "title": item.get("jobTitle", "Untitled role"),
                "company": item.get("companyName", "Unknown company"),
                "url": item.get("url", ""),
                "description": (item.get("jobExcerpt") or "")[:500],
                "tags": item.get("jobIndustry", ""),
                "source": "Jobicy",
            })
    return jobs


def fetch_himalayas_jobs():
    """Himalayas: remote jobs, queried per keyword since search takes a single query string."""
    jobs = []
    for term in HIMALAYAS_SEARCH_TERMS:
        try:
            resp = requests.get(
                "https://himalayas.app/jobs/api/search",
                params={"q": term},
                headers=REQUEST_HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[Himalayas] fetch failed for '{term}': {e}")
            continue

        for item in data.get("jobs", []):
            guid = item.get("guid") or item.get("id")
            jobs.append({
                "id": f"himalayas_{guid}",
                "title": item.get("title", "Untitled role"),
                "company": (item.get("companyName")
                            or item.get("company", {}).get("name", "Unknown company")
                            if isinstance(item.get("company"), dict) else item.get("company", "Unknown company")),
                "url": item.get("applicationLink") or item.get("url", ""),
                "description": (item.get("excerpt") or item.get("description") or "")[:500],
                "tags": " ".join(item.get("categories", []) or []),
                "source": "Himalayas",
            })
    return jobs


# ---------- FILTER ----------

def matches_keywords(job):
    haystack = f"{job['title']} {job['tags']} {job['description']}".lower()
    return any(kw in haystack for kw in KEYWORDS)


# ---------- DISCORD ----------

def post_to_discord(job):
    if not DISCORD_WEBHOOK_URL:
        print("No DISCORD_WEBHOOK_URL set — skipping post, printing instead:")
        print(job)
        return

    embed = {
        "title": job["title"][:256],
        "url": job["url"],
        "description": job["description"] or "No description provided.",
        "color": 5814783,
        "fields": [
            {"name": "Company", "value": job["company"] or "See listing", "inline": True},
            {"name": "Source", "value": job["source"], "inline": True},
        ],
        "footer": {"text": "Fresh job alert 🚨"},
    }

    payload = {"embeds": [embed]}

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if resp.status_code >= 300:
            print(f"[Discord] failed ({resp.status_code}): {resp.text}")
        else:
            print(f"[Discord] posted: {job['title']}")
    except Exception as e:
        print(f"[Discord] error posting: {e}")

    time.sleep(1)  # be nice to Discord rate limits


# ---------- MAIN ----------

def dedupe_across_sources(jobs):
    """Same job can appear on 2+ boards (e.g. Arbeitnow re-lists Greenhouse jobs).
    Collapse by normalized title+company so we don't post the same role twice."""
    unique = {}
    for job in jobs:
        key = (job["title"].strip().lower(), job["company"].strip().lower())
        if key not in unique:
            unique[key] = job
    return list(unique.values())


def main():
    seen = load_seen()

    all_jobs = (
        fetch_remoteok_jobs()
        + fetch_wwr_jobs()
        + fetch_arbeitnow_jobs()
        + fetch_jobicy_jobs()
        + fetch_himalayas_jobs()
    )
    print(f"Fetched {len(all_jobs)} total jobs from all sources.")

    all_jobs = dedupe_across_sources(all_jobs)
    print(f"{len(all_jobs)} after cross-source dedup.")

    new_matches = [
        job for job in all_jobs
        if job["id"] not in seen and matches_keywords(job)
    ]
    print(f"Found {len(new_matches)} new matching jobs.")

    for job in new_matches:
        post_to_discord(job)
        seen.add(job["id"])

    save_seen(seen)


if __name__ == "__main__":
    main()
