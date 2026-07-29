# Generate your `config.json` from your CV (no coding)

Copy **everything in the box below**, paste it into your favorite chatbot
(ChatGPT, Claude, Gemini, Copilot…), then attach or paste **your CV/résumé** and
a line about **where you want to work**. The model returns a finished
`config.json` — save it over the `config.json` in your repo and commit it.

> Tip: also tell it anything special, e.g. "only senior roles", "no startups",
> "exclude pharma", "I also do data science", "remote only".

---

```
You are configuring a personal job-search tracker. Read my CV (below) and my
location preferences, then output a SINGLE JSON object — valid config.json,
nothing else, no markdown fences, no commentary.

The tracker scrapes job boards (LinkedIn, Indeed, Glassdoor, ZipRecruiter,
Google Jobs, HiringCafe, USAJOBS, etc.), keeps postings
whose TITLE matches my keywords, and shows them on a dashboard. Matching is
case-insensitive substring on the job title.

Produce this exact shape, filled in for ME based on my CV:

{
  "profile": {
    "title": "<short name for my tracker, e.g. 'Data Science Job Tracker'>",
    "subtitle": "<my target locations, e.g. 'Bay Area · Remote'>",
    "emoji": "<one relevant emoji>"
  },
  "keywords": {
    "include": [ "<20-60 job-TITLE phrases that fit my field>" ],
    "exclude": [ "<titles to drop: intern, internship, postdoc, etc., plus any roles clearly NOT for me>" ]
  },
  "search_terms": {
    "linkedin": [ "<15-25 queries to type into LinkedIn search>" ],
    "indeed":   [ "<6-10 broad queries for Indeed>" ],
    "glassdoor": [ "<6-10 broad queries for Glassdoor>" ],
    "ziprecruiter": [ "<6-10 broad queries for ZipRecruiter>" ],
    "google_jobs": [ "<6-10 broad queries for Google Jobs>" ],
    "hiring_cafe": [ "<6-10 broad queries for HiringCafe>" ]
  },
  "locations": {
    "linkedin": [ { "name": "<label>", "location": "<City/Region, State, Country>", "geoId": "" } ],
    "indeed":   [ { "location": "<City, ST  OR  State>", "country": "USA" } ],
    "glassdoor": [ { "location": "<City, ST  OR  State>", "country": "USA" } ],
    "ziprecruiter": [ { "location": "<City, ST  OR  State>", "country": "USA" } ],
    "google_jobs": [ { "location": "<City, ST  OR  State>", "country": "USA" } ],
    "hiring_cafe": [ { "location": "<Country, State, or City>" } ]
  },
  "google_jobs": {
    "queries": [],
    "serpapi_api_key": "",
    "oxylabs_username": "",
    "oxylabs_password": ""
  },
  "hiring_cafe": {
    "max_pages": 3
  },
  "employers": {
    "priority": [ "<optional: organizations I'd love to work for; [] if none>" ],
    "exclude":  [ "<optional: company-name substrings to always drop, e.g. recruiting agencies; [] if none>" ]
  },
  "priority_topics": {
    "terms": [ [ "<topic label>", "<a JS regex matching it>" ] ]
  },
  "role_categories": {
    "terms": [ [ "<role bucket label>", "<a JS regex matching titles in that bucket>" ] ]
  },
  "notify": { "min_fit": 75 }
}

Rules:
- keywords.include: use FULL words/phrases as they appear in real titles
  ("data scientist", "machine learning engineer"), not stems. Multi-word phrases
  match as substrings. Be specific enough to avoid unrelated fields.
- keywords.exclude: always include intern/internship/co-op/trainee; add seniority
  or off-field terms if I asked (e.g. "junior", "manager", a competing field).
- search_terms are broader than keywords (they're what you'd type in a search box).
- locations: convert my target places to the format shown. For LinkedIn, set
  "geoId": "" unless I gave you one — the tracker resolves the text. Use a
  separate entry per place. For Indeed/Glassdoor/ZipRecruiter/Google Jobs,
  "country" is "USA", "Australia", "Canada", "GB", etc. HiringCafe's public
  search route currently defaults to United States, so keep its location as
  "United States" unless I explicitly ask otherwise.
- google_jobs.queries: keep [] unless I explicitly provide exact Google Jobs
  search-box text to use verbatim.
- google_jobs API credentials: keep serpapi_api_key, oxylabs_username, and
  oxylabs_password empty; these should be GitHub Actions secrets, not generated
  into config.json, unless I explicitly ask for local-only config credentials.
- hiring_cafe: keep the default max_pages unless I ask for deeper searches.
- priority_topics: 3-6 of MY standout specialties/skills (these get starred &
  filterable). Each regex is a plain JavaScript regex source string (no slashes,
  no flags). Escape backslashes for JSON (write \\b not \b).
- role_categories: 5-9 buckets that group the kinds of roles I'd see, ordered
  most-specific first. Same regex rules. The dashboard's Role filter uses these.
- Output ONLY the JSON object.

MY CV:
<paste your CV here, or attach it>

MY TARGET LOCATIONS / PREFERENCES:
<e.g. "San Francisco Bay Area and remote; senior IC roles; no agencies">
```

---

## Optional: better LinkedIn location filtering (`geoId`)

`geoId: ""` works for most city/metro searches (LinkedIn resolves the text). For
tighter filtering you can fill in the numeric geoId. A few common ones:

| Place | geoId |
|---|---|
| United States | `103644278` |
| San Francisco Bay Area | `90000084` |
| California | `102095887` |
| New York City Metro | `90000070` |
| Greater Boston | `90000007` |
| Greater Seattle | `90000091` |
| United Kingdom | `101165590` |
| Canada | `101174742`* |
| Australia | `101452733` |

To find another: open LinkedIn job search, pick your location, and copy the
`geoId=` value from the URL. (*Region geoIds occasionally drift — verify by
checking that a search returns jobs from the right place.)

## Don't want to use an LLM?

Just edit `config.json` by hand — it's commented and self-explanatory. The two
things most people change: `keywords.include` / `search_terms` (what roles) and
`locations` (where). Everything else is optional.
