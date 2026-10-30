import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

from company_directory import (
    load_company_directory,
    record_company,
    save_company_directory,
    normalize_company_key,
    extract_career_root_url,
)
from resolve_ats import slugify_company

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def probe_greenhouse(slug: str) -> str:
    """Probes Greenhouse for a company slug. Returns career URL or empty."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=4) as res:
            if res.status == 200:
                return f"https://job-boards.greenhouse.io/{slug}"
    except Exception:
        pass
    return ""

def probe_ashby(slug: str) -> str:
    """Probes Ashby for a company slug. Returns career URL or empty."""
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=4) as res:
            if res.status == 200:
                data = json.loads(res.read().decode("utf-8"))
                if data.get("jobs"):
                    return f"https://jobs.ashbyhq.com/{slug}"
    except Exception:
        pass
    return ""

def probe_lever(slug: str) -> str:
    """Probes Lever for a company slug. Returns career URL or empty."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=4) as res:
            if res.status == 200:
                data = json.loads(res.read().decode("utf-8"))
                if isinstance(data, list) and len(data) > 0:
                    return f"https://jobs.lever.co/{slug}"
    except Exception:
        pass
    return ""

def search_workday_ddg(company_name: str) -> str:
    """Searches DuckDuckGo HTML for a company's Workday career portal."""
    query = f"{company_name} careers workday"
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            html = res.read().decode("utf-8", errors="ignore")
            matches = re.findall(r'href="([^"]+)"', html)
            for m in matches:
                target = ""
                if "duckduckgo.com/l/?uddg=" in m:
                    u = m.split("uddg=")[1].split("&")[0]
                    target = urllib.parse.unquote(u)
                elif m.startswith("http"):
                    target = m
                if "myworkdayjobs.com" in target:
                    root, ats = extract_career_root_url(target)
                    if root and ats == "Workday":
                        return root
    except Exception:
        pass
    return ""

def resolve_single_company(company_name: str) -> tuple[str, str, str]:
    """
    Tries Tier 1 (Greenhouse, Ashby, Lever slugs) then Tier 2 (Workday search).
    Returns (company_name, career_url, ats_platform).
    """
    slugs = slugify_company(company_name)
    
    # 1. Probe Greenhouse
    for s in slugs:
        gh_url = probe_greenhouse(s)
        if gh_url:
            return company_name, gh_url, "Greenhouse"

    # 2. Probe Ashby
    for s in slugs:
        ashby_url = probe_ashby(s)
        if ashby_url:
            return company_name, ashby_url, "Ashby"

    # 3. Probe Lever
    for s in slugs:
        lever_url = probe_lever(s)
        if lever_url:
            return company_name, lever_url, "Lever"

    # 4. Probe Workday via search
    wd_url = search_workday_ddg(company_name)
    if wd_url:
        return company_name, wd_url, "Workday"

    return company_name, "", ""

if __name__ == "__main__":
    test_list = ["NVIDIA", "Figma", "Stripe", "Anthropic", "PwC", "Databricks", "Nike", "Cisco", "Palantir", "Discord"]
    print("Testing 10 companies...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(resolve_single_company, c): c for c in test_list}
        for future in as_completed(futures):
            c_name, c_url, c_ats = future.result()
            print(f"  {c_name:<15}: [{c_ats}] {c_url}")
