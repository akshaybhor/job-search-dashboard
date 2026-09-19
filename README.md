# 🚀 Automated Job Search & Triage Dashboard

An automated pipeline of GitHub Actions workflows that scrapes **Backend Engineering, C++, Data Engineering, and Junior AI/ML roles** across multiple job boards, evaluates them against your candidate profile using an AI agent, and surfaces the best matches in an interactive dashboard.


## What It Does

This repo runs completely autonomously on GitHub Actions to build a live, constantly-updating database of jobs tailored to your exact profile. 

### 1. Job Scraping Watchers (Hourly / Daily)
Multiple scrapers run throughout the day to pull in fresh roles:
- **LinkedIn Watcher:** Hits LinkedIn's public guest endpoint every hour for roles posted in the last 1h.
- **Indeed Watcher:** Uses `python-jobspy` to pull Indeed jobs every hour.
- **Startup / Biotech Direct ATS:** Scans direct ATS boards (Greenhouse, Workday, Lever, Ashby) for specific curated companies.
- **Government Boards:** Scans USAJobs, GovernmentJobs, and CalCareers for public sector roles.
- **ZipRecruiter & Google Jobs:** Sweeps aggregator boards twice daily.

All jobs are deduped, normalized, and merged into a central `all_jobs.json` database. Jobs older than 14 days are automatically pruned to keep the database fresh.

### 2. Nightly AI Triage Agent (`triage_agent.py`)
Every night, the **Triage Agent** wakes up to score all newly scraped jobs against your private resume and candidate profile.
- It uses a **multi-model relay race** to completely bypass free tier limits, chaining together multiple API keys (e.g., `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `GROQ_API_KEY`) to score up to 300 jobs per night completely for free.
- It generates a fit score (0-100), extracts red flags, and even generates outreach openers for the jobs.
- The results are pushed to `scores.json` so you can sort the dashboard by "AI Fit Score".

### 3. Interactive Triage Dashboard (`triage.html`)
A single-page React-style HTML dashboard hosted on GitHub Pages that merges all the JSON data into a beautiful, filterable UI.
- Sort by AI Fit Score, Post Date, or Salary.
- Filter by Seniority, Source, or Role Type.
- Save, Apply, or Dismiss roles (state is saved safely to your local browser storage).

## Targeted Roles & Keywords
The scrapers are heavily customized to filter out noise and target specific roles:
- **Backend / Systems:** `backend engineer`, `distributed systems`, `c++ engineer`, `api engineer`
- **Data Engineering:** `data engineer`, `etl developer`, `data platform`
- **Cloud / Infra:** `platform engineer`, `sre`, `cloud engineer`
- **AI / ML (Junior/Entry Focus):** `junior ai engineer`, `associate machine learning engineer`, `llm engineer`

**Excluded:** Seniority filters automatically drop titles containing `staff`, `principal`, `director`, `vp`, or `head of`.

## Setup & Configuration

### GitHub Secrets
To power the Nightly Triage Agent, add these secrets to your repository (**Settings → Secrets and variables → Actions**):

| Secret | Value |
|---|---|
| `GEMINI_API_KEY_1` | First free Gemini API key (`gemini-3.1-flash-lite`) |
| `GEMINI_API_KEY_2` | Second free Gemini API key (fallback) |
| `GROQ_API_KEY` | Groq API key (`openai/gpt-oss-120b` fallback) |
| `CANDIDATE_PROFILE` | Your specific candidate requirements & target roles |
| `CANDIDATE_RESUME` | Your raw resume text |

### Manual Workflows
You can trigger any workflow manually from the **Actions** tab on GitHub:
- **Nightly Job Triage:** Run the AI scorer manually.
- **Manual Database Cleanup:** Select a dropdown to keep jobs from the past X days (or 0 to wipe the database clean).
- **Test Gemini API:** Verify your API keys are working correctly.

## Repo Structure

```text
├── scrape_jobs.py                  # Core scraping engine for all boards
├── discover.py                     # Startup discovery script
├── triage_agent.py                 # AI fit-scoring agent (Gemini / Groq / Anthropic)
├── requirements.txt                # Python dependencies (python-jobspy)
├── all_jobs.json                   # Cumulative master job database
├── scores.json                     # AI agent verdicts and scores
├── triage.html                     # Interactive frontend dashboard
└── .github/workflows/
    ├── scrape_jobs.yml             # Daily scraper runner
    ├── linkedin_watch.yml          # Hourly LinkedIn scraper
    ├── indeed_watch.yml            # Hourly Indeed scraper
    ├── triage.yml                  # Nightly AI scoring runner (relay race)
    ├── cleanup_db.yml              # Manual database cleanup tool
    └── test_gemini_api.yml         # API key validation tool
```
