"""
scrape_direct_ats.py — Automated Direct ATS Scraper.
Periodically probes Greenhouse, Ashby, and Lever public APIs for target employers
cataloged in companies.json. Extracts 100% direct application URLs, parses timestamps,
filters for engineering roles, and merges them directly into all_jobs.json.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Import domain filters and database merge helper from existing codebase
from scrape_jobs import (
    is_mle_role,
    is_excluded_company,
    is_excluded_location,
    is_dealbreaker_role,
    EXCLUDED_CLEARANCE_RE,
    EXCLUDED_SENIORITY_RE,
    _merge_into_all_jobs,
)
from company_directory import (
    load_company_directory,
    save_company_directory,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def parse_iso_or_epoch_to_dt(val) -> datetime:
    """Safely converts ISO string or unix epoch ms to a UTC datetime object."""
    if not val:
        return None
    try:
        if isinstance(val, (int, float)):
            # Epoch milliseconds
            return datetime.fromtimestamp(val / 1000.0, tz=timezone.utc)
        s = str(val).strip()
        if s.isdigit():
            return datetime.fromtimestamp(int(s) / 1000.0, tz=timezone.utc)
        # ISO string parsing
        # Normalize trailing Z
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def is_job_fresh(dt: datetime, max_hours: int = 48) -> bool:
    """Returns True if the datetime is within max_hours of now."""
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    age = (now - dt).total_seconds() / 3600.0
    return 0 <= age <= max_hours


def probe_greenhouse_company(company_name: str, slug: str, max_lookback_hours: int = 48) -> list[dict]:
    """Scrapes fresh matching jobs from a company's Greenhouse board."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"    [Greenhouse error: {slug}] {e}")
        return []

    jobs = []
    for item in data.get("jobs", []):
        title = item.get("title", "").strip()
        if not title or not is_mle_role(title):
            continue
        if EXCLUDED_SENIORITY_RE.search(title):
            continue

        # Check description for clearance and no-sponsorship dealbreakers
        content = item.get("content", "") or ""
        if EXCLUDED_CLEARANCE_RE.search(content) or is_dealbreaker_role(title, content):
            continue

        # Location filtering: reject non-US / foreign locations
        loc_data = item.get("location") or {}
        location = (loc_data.get("name") or "").strip() or "United States"
        if is_excluded_location(location):
            continue
        offices = [o.get("name") for o in item.get("offices", []) if o.get("name")]
        if offices and all(is_excluded_location(o) for o in offices):
            continue

        # Freshness check
        pub_dt = parse_iso_or_epoch_to_dt(item.get("first_published")) or parse_iso_or_epoch_to_dt(item.get("updated_at"))
        if max_lookback_hours > 0 and not is_job_fresh(pub_dt, max_lookback_hours):
            continue

        date_posted = pub_dt.strftime("%Y-%m-%d") if pub_dt else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        workplace = (item.get("workplaceType") or "").lower()
        is_remote = bool("remote" in location.lower() or workplace == "remote")
        apply_url = item.get("absolute_url") or f"https://job-boards.greenhouse.io/{slug}/jobs/{item.get('id')}"

        jobs.append({
            "company": company_name,
            "title": title,
            "location": location,
            "url": apply_url,
            "date_posted": date_posted,
            "ats": "Greenhouse",
            "remote": is_remote,
            "direct_url": apply_url,
            "source": "direct_ats",
        })
    return jobs


def probe_ashby_company(company_name: str, slug: str, max_lookback_hours: int = 48) -> list[dict]:
    """Scrapes fresh matching jobs from a company's Ashby board."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"    [Ashby error: {slug}] {e}")
        return []

    jobs = []
    for item in data.get("jobs", []):
        if not item.get("isListed", True):
            continue

        title = item.get("title", "").strip()
        if not title or not is_mle_role(title):
            continue
        if EXCLUDED_SENIORITY_RE.search(title):
            continue

        content = item.get("descriptionPlain", "") or ""
        if EXCLUDED_CLEARANCE_RE.search(content) or is_dealbreaker_role(title, content):
            continue

        # Location filtering
        location = (item.get("location") or "").strip() or "United States"
        address_country = (
            (item.get("address") or {})
            .get("postalAddress", {})
            .get("addressCountry", "")
        )
        if is_excluded_location(location) or is_excluded_location(address_country):
            continue

        pub_dt = parse_iso_or_epoch_to_dt(item.get("publishedAt"))
        if max_lookback_hours > 0 and not is_job_fresh(pub_dt, max_lookback_hours):
            continue

        date_posted = pub_dt.strftime("%Y-%m-%d") if pub_dt else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        workplace = (item.get("workplaceType") or "").lower()
        is_remote = bool(item.get("isRemote") or "remote" in location.lower() or workplace == "remote")
        apply_url = item.get("jobUrl") or item.get("applyUrl") or f"https://jobs.ashbyhq.com/{slug}/{item.get('id')}"

        jobs.append({
            "company": company_name,
            "title": title,
            "location": location,
            "url": apply_url,
            "date_posted": date_posted,
            "ats": "Ashby",
            "remote": is_remote,
            "direct_url": apply_url,
            "source": "direct_ats",
        })
    return jobs


def probe_lever_company(company_name: str, slug: str, max_lookback_hours: int = 48) -> list[dict]:
    """Scrapes fresh matching jobs from a company's Lever board."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8"))
            if not isinstance(data, list):
                return []
    except Exception as e:
        print(f"    [Lever error: {slug}] {e}")
        return []

    jobs = []
    for item in data:
        title = item.get("text", "").strip()
        if not title or not is_mle_role(title):
            continue
        if EXCLUDED_SENIORITY_RE.search(title):
            continue

        content = item.get("descriptionPlain", "") or ""
        if EXCLUDED_CLEARANCE_RE.search(content) or is_dealbreaker_role(title, content):
            continue

        # Location filtering
        categories = item.get("categories") or {}
        location = (categories.get("location") or "").strip() or "United States"
        if is_excluded_location(location):
            continue

        pub_dt = parse_iso_or_epoch_to_dt(item.get("createdAt"))
        if max_lookback_hours > 0 and not is_job_fresh(pub_dt, max_lookback_hours):
            continue

        date_posted = pub_dt.strftime("%Y-%m-%d") if pub_dt else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        workplace = (item.get("workplaceType") or "").lower()
        is_remote = bool("remote" in location.lower() or workplace == "remote")
        apply_url = item.get("hostedUrl") or item.get("applyUrl") or f"https://jobs.lever.co/{slug}/{item.get('id')}"

        jobs.append({
            "company": company_name,
            "title": title,
            "location": location,
            "url": apply_url,
            "date_posted": date_posted,
            "ats": "Lever",
            "remote": is_remote,
            "direct_url": apply_url,
            "source": "direct_ats",
        })
    return jobs


def is_workday_fresh(posted_on: str, max_lookback_hours: int = 48) -> bool:
    """Checks whether a Workday 'postedOn' string falls within the lookback window."""
    if not posted_on:
        return True
    s = str(posted_on).lower().strip()
    if "today" in s or "just posted" in s:
        return True
    if "yesterday" in s:
        return max_lookback_hours >= 24
    m = re.search(r"(\d+)\s+day", s)
    if m:
        days = int(m.group(1))
        return (days * 24) <= max_lookback_hours
    if "hour" in s or "minute" in s:
        return True
    if "30+" in s or "month" in s or "week" in s:
        return False
    try:
        dt = parse_iso_or_epoch_to_dt(posted_on)
        if dt:
            return is_job_fresh(dt, max_lookback_hours)
    except Exception:
        pass
    return False


def probe_workday_company(company_name: str, career_url: str, max_lookback_hours: int = 48) -> list[dict]:
    """Scrapes fresh matching engineering roles from a company's Workday CXS API."""
    if not career_url:
        return []

    parsed = urllib.parse.urlparse(career_url)
    netloc = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if "/wday/cxs/" in career_url:
        m = re.search(r"/wday/cxs/([^/]+)/([^/]+)/jobs", career_url)
        if not m:
            return []
        cxs_url = career_url
        base_url = f"https://{netloc}/{m.group(2)}"
    else:
        parts = path.split("/")
        site = parts[0] if parts and parts[0] else "careers"
        tenant = netloc.split(".")[0]
        cxs_url = f"https://{netloc}/wday/cxs/{tenant}/{site}/jobs"
        base_url = f"https://{netloc}/{site}"

    terms = ["software engineer", "machine learning", "data engineer", "backend", "ai engineer"]
    seen: dict[str, dict] = {}

    for term in terms:
        time.sleep(0.3)
        body = json.dumps({"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": term}).encode("utf-8")
        req = urllib.request.Request(
            cxs_url,
            data=body,
            headers={**HEADERS, "Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                data = json.loads(res.read().decode("utf-8"))
        except Exception:
            continue

        postings = data.get("jobPostings", [])
        for posting in postings:
            ext_path = posting.get("externalPath", "")
            if not ext_path or ext_path in seen:
                continue
            title = posting.get("title", "")
            if not is_mle_role(title) or EXCLUDED_SENIORITY_RE.search(title):
                continue

            posted_on = posting.get("postedOn", "")
            if not is_workday_fresh(posted_on, max_lookback_hours):
                continue

            loc = posting.get("locationsText", "") or "United States"
            if is_excluded_location(loc):
                continue

            job_url = f"{base_url}{ext_path}"
            is_remote = bool("remote" in loc.lower() or "remote" in title.lower())

            seen[ext_path] = {
                "company": company_name,
                "title": title,
                "location": loc,
                "url": job_url,
                "date_posted": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "ats": "Workday",
                "remote": is_remote,
                "direct_url": job_url,
                "source": "direct_ats",
            }

    return list(seen.values())


def run_direct_ats_scraper(lookback_hours: int = 48, max_companies: int = 100) -> list[dict]:
    """
    Scans cataloged companies from companies.json, fetches fresh roles via direct APIs,
    and merges them into all_jobs.json. Supports Greenhouse, Ashby, Lever, and Workday.
    """
    comp_data = load_company_directory()
    companies = comp_data.get("companies", {})
    if not companies:
        print("[Direct ATS] No companies found in companies.json.")
        return []

    # Select candidate companies that use Greenhouse, Ashby, Lever, or Workday
    target_list = []
    for key, c in companies.items():
        c_name = c.get("name", key)
        if is_excluded_company(c_name):
            continue
        ats = (c.get("ats") or "").strip()
        career_url = (c.get("career_url") or "").strip()
        if not career_url:
            continue
        if ats in ("Greenhouse", "Ashby", "Lever", "Workday"):
            slug = career_url.rstrip("/").split("/")[-1] if ats != "Workday" else ""
            target_list.append({
                "name": c_name,
                "ats": ats,
                "slug": slug,
                "career_url": career_url,
                "last_seen": c.get("last_seen", ""),
                "key": key,
            })

    # Prioritize by recency
    target_list.sort(key=lambda x: x.get("last_seen", ""), reverse=True)
    batch = target_list[:max_companies]

    print(f">>> [Direct ATS Scraper] Scanning {len(batch)} companies (lookback: {lookback_hours}h)...")
    surfaced_jobs = []

    for item in batch:
        c_name = item["name"]
        ats = item["ats"]
        slug = item["slug"]
        career_url = item.get("career_url", "")
        time.sleep(0.4)  # Polite throttle

        found = []
        if ats == "Greenhouse":
            found = probe_greenhouse_company(c_name, slug, max_lookback_hours=lookback_hours)
        elif ats == "Ashby":
            found = probe_ashby_company(c_name, slug, max_lookback_hours=lookback_hours)
        elif ats == "Lever":
            found = probe_lever_company(c_name, slug, max_lookback_hours=lookback_hours)
        elif ats == "Workday":
            found = probe_workday_company(c_name, career_url, max_lookback_hours=lookback_hours)

        if found:
            print(f"  [+] {c_name} ({ats}): +{len(found)} fresh role(s)")
            surfaced_jobs.extend(found)
        else:
            print(f"  [-] {c_name} ({ats}): 0 new roles in window")

    print(f"\n[Direct ATS Scraper] Total fresh roles surfaced: {len(surfaced_jobs)}")

    if surfaced_jobs:
        added = _merge_into_all_jobs(surfaced_jobs)
        print(f"[Direct ATS Scraper] Master DB: {added} new unique roles merged.")

    return surfaced_jobs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Direct ATS Scraper for Greenhouse, Ashby, Lever, and Workday")
    parser.add_argument("--lookback", type=int, default=48, help="Lookback window in hours (default: 48)")
    parser.add_argument("--limit", type=int, default=100, help="Max companies to scan per run (default: 100)")
    args = parser.parse_args()

    run_direct_ats_scraper(lookback_hours=args.lookback, max_companies=args.limit)
