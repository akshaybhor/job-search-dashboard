"""
resolve_ats.py — Automated Direct ATS Link Resolver.
Given a job posting (e.g. from LinkedIn), checks if the company uses Greenhouse,
Lever, or Ashby, finds the direct ATS application link for that role,
and registers the company's root career portal into companies.json.
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
from company_directory import (
    load_company_directory,
    record_company,
    save_company_directory,
    normalize_company_key,
)
try:
    from scrape_jobs import is_excluded_company
except ImportError:
    def is_excluded_company(name: str) -> bool:
        return False


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def slugify_company(company_name: str) -> list[str]:
    """Generates candidate slugs for a company name."""
    if not company_name:
        return []
    clean = company_name.lower().strip()
    clean = re.sub(r"[\.,'\"\(\)]", "", clean)
    clean = re.sub(r"\b(inc|llc|corp|corporation|ltd|co|technologies|holdings|plc)\b", "", clean).strip()

    slugs = []
    # 1. pure alphanumeric without spaces
    s1 = re.sub(r"\s+", "", clean)
    if s1:
        slugs.append(s1)
    # 2. hyphenated
    s2 = re.sub(r"\s+", "-", clean)
    if s2 and s2 != s1:
        slugs.append(s2)
    # 3. underscored
    s3 = re.sub(r"\s+", "_", clean)
    if s3 and s3 not in slugs:
        slugs.append(s3)
    return slugs


def check_greenhouse_board(slug: str) -> list[dict]:
    """Queries Greenhouse public API for a company slug."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data.get("jobs", [])
    except Exception:
        return []


def check_ashby_board(slug: str) -> list[dict]:
    """Queries Ashby public posting API for a company slug."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data.get("jobs", [])
    except Exception:
        return []


def check_lever_board(slug: str) -> list[dict]:
    """Queries Lever public API for a company slug."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        return []


def title_similarity(t1: str, t2: str) -> float:
    """Computes simple word-overlap Jaccard score between two titles."""
    w1 = set(re.findall(r"\w+", t1.lower()))
    w2 = set(re.findall(r"\w+", t2.lower()))
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


def resolve_direct_ats(company_name: str, job_title: str) -> tuple[str, str, str]:
    """
    Attempts to discover direct ATS application link for a company and title.
    Returns (direct_url, ats_platform, root_career_url).
    """
    if not company_name or is_excluded_company(company_name):
        return "", "", ""
    slugs = slugify_company(company_name)
    if not slugs:
        return "", "", ""

    for slug in slugs:
        # 1. Try Greenhouse
        gh_jobs = check_greenhouse_board(slug)
        if gh_jobs:
            best_match = None
            best_score = 0.0
            for j in gh_jobs:
                score = title_similarity(job_title, j.get("title", ""))
                if score > best_score:
                    best_score = score
                    best_match = j
            if best_match and best_score >= 0.4:
                return (
                    best_match.get("absolute_url", ""),
                    "Greenhouse",
                    f"https://job-boards.greenhouse.io/{slug}",
                )
            elif gh_jobs:
                # Board exists even if specific role wasn't found
                return "", "Greenhouse", f"https://job-boards.greenhouse.io/{slug}"

        # 2. Try Ashby
        ashby_jobs = check_ashby_board(slug)
        if ashby_jobs:
            best_match = None
            best_score = 0.0
            for j in ashby_jobs:
                score = title_similarity(job_title, j.get("title", ""))
                if score > best_score:
                    best_score = score
                    best_match = j
            if best_match and best_score >= 0.4:
                return (
                    best_match.get("jobUrl", ""),
                    "Ashby",
                    f"https://jobs.ashbyhq.com/{slug}",
                )
            elif ashby_jobs:
                return "", "Ashby", f"https://jobs.ashbyhq.com/{slug}"

        # 3. Try Lever
        lever_jobs = check_lever_board(slug)
        if lever_jobs:
            best_match = None
            best_score = 0.0
            for j in lever_jobs:
                score = title_similarity(job_title, j.get("text", ""))
                if score > best_score:
                    best_score = score
                    best_match = j
            if best_match and best_score >= 0.4:
                return (
                    best_match.get("hostedUrl", ""),
                    "Lever",
                    f"https://jobs.lever.co/{slug}",
                )
            elif lever_jobs:
                return "", "Lever", f"https://jobs.lever.co/{slug}"

    return "", "", ""


def enrich_jobs(all_jobs_path: str = None, max_companies: int = 50) -> int:
    """
    Enriches all_jobs.json with direct ATS URLs and updates companies.json.
    Processes newly added companies to discover their direct ATS board.
    """
    if not all_jobs_path:
        all_jobs_path = os.path.join(SCRIPT_DIR, "all_jobs.json")
    if not os.path.exists(all_jobs_path):
        print(f"File not found: {all_jobs_path}")
        return 0

    with open(all_jobs_path, "r", encoding="utf-8") as f:
        all_data = json.load(f)

    jobs = all_data.get("jobs", [])
    comp_dir = load_company_directory()
    existing_companies = comp_dir.get("companies", {})

    print(f"Scanning {len(jobs)} jobs for direct ATS resolution...")
    probed = 0
    resolved = 0

    # Collect unique companies without confirmed direct ATS
    seen_companies = set()
    for j in jobs:
        c_name = j.get("company", "").strip()
        if not c_name or c_name.lower() == "unknown" or c_name in seen_companies or is_excluded_company(c_name):
            continue
        seen_companies.add(c_name)

        comp_key = normalize_company_key(c_name)
        # Skip if already resolved with a major ATS
        if comp_key in existing_companies:
            ats_plat = existing_companies[comp_key].get("ats", "")
            if ats_plat in ("Workday", "Greenhouse", "Lever", "Ashby", "iCIMS"):
                continue

        # Probe Greenhouse, Ashby, Lever
        probed += 1
        direct_url, ats_plat, root_url = resolve_direct_ats(c_name, j.get("title", ""))
        if root_url and ats_plat:
            record_company(
                c_name,
                root_url,
                date_seen=j.get("date_posted"),
                ats_hint=ats_plat,
                directory_data=comp_dir,
            )
            resolved += 1
            print(f"  [Discovered ATS] {c_name} -> {ats_plat} ({root_url})")

        time.sleep(0.3)
        if probed >= max_companies:
            break

    if resolved > 0:
        save_company_directory(comp_dir)
        print(f"[OK] Saved {resolved} newly resolved companies to companies.json")

    return resolved


if __name__ == "__main__":
    import sys
    if "--enrich" in sys.argv:
        enrich_jobs()
    else:
        test_resolver()
