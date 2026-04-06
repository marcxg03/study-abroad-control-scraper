# ARCHITECTURE.md
# Reddit Control Group Scraper

## 1. Tech Stack Decisions

### Framework: Streamlit
- **What it is**: A Python library that turns scripts into interactive web apps with minimal code
- **Why we chose it**: Lab members already run Python locally; Streamlit requires no web development knowledge; the team has prior experience with it
- **How to run**: `python3 -m streamlit run app.py`

### Language: Python 3.10+
- **Why**: ArcticShift API calls, data processing, and CSV export are all naturally Python tasks. No JavaScript needed.

### HTTP Client: `httpx` (with `asyncio`)
- **What it is**: A Python library for making requests to external APIs. `asyncio` lets those requests run in the background without freezing the UI.
- **Why not `requests`**: The standard `requests` library blocks — it freezes the program while waiting for a response. `httpx` with async support lets scraping run in the background while Streamlit stays responsive.

### Data Processing: `pandas`
- **What it is**: A Python library for working with tabular data — think of it as Excel for Python
- **Why**: Deduplication, CSV export, and filtering are all trivially easy with pandas

### Storage: Local filesystem only
- **Why**: No database needed. User lists and scraped posts are written directly to CSV files in an `/output` folder. Keeps setup dead simple.

### State Management: Streamlit Session State
- **What it is**: A built-in Streamlit feature that lets the app remember things between interactions (like which users have been identified, or how far a scrape has progressed)
- **Why**: No external state management library needed for an app of this complexity

---

## 2. File and Folder Structure

```
reddit_control_scraper/
│
├── app.py                  # Main entry point — launches the Streamlit app
│
├── requirements.txt        # All Python packages needed to run the app
│
├── README.md               # Setup instructions for lab members
│
├── config.py               # Central config file: keywords, subreddit names, default sample sizes, API base URL
│
├── modules/
│   ├── __init__.py         # Makes this folder a Python package (required boilerplate)
│   ├── identifier.py       # User identification logic for all three groups
│   ├── scraper.py          # Post history scraping logic (calls ArcticShift API)
│   ├── exporter.py         # CSV export logic — formats and writes output files
│   └── arctic_api.py       # Low-level ArcticShift API wrapper — all HTTP calls live here
│
├── pages/
│   ├── 01_primary_control.py       # Streamlit page: Primary Control (r/studyAbroad)
│   ├── 02_secondary_control_a.py   # Streamlit page: Secondary Control A (r/REU)
│   └── 03_secondary_control_b.py   # Streamlit page: Secondary Control B (r/college)
│
├── output/                 # Auto-created at runtime — all CSV exports land here
│   ├── primary_control_studyAbroad.csv
│   ├── secondary_control_REU.csv
│   └── secondary_control_college.csv
│
└── logs/                   # Auto-created at runtime — run logs land here
    └── run_YYYY-MM-DD_HH-MM.log
```

---

## 3. Module Map

Each module has exactly one job. This is intentional — it makes debugging much easier.

| Module | Single Responsibility |
|---|---|
| `app.py` | Launch the app, render the home screen with three group cards |
| `config.py` | Store all hardcoded values — keywords, subreddit names, API URL, defaults |
| `arctic_api.py` | Make HTTP requests to ArcticShift — handle retries, rate limiting, pagination |
| `identifier.py` | Apply filtering logic to raw API results to produce a clean user list |
| `scraper.py` | Take a user list, fetch full post history for each user, return structured data |
| `exporter.py` | Take structured post data, deduplicate, and write to CSV |

---

## 4. ArcticShift API Contract

All HTTP calls go through `arctic_api.py`. No other module talks to the API directly.

**Base URL**: `https://arctic-shift.photon-reddit.com`

### Endpoints Used

#### Get all posts from a subreddit (for user identification)
```
GET /api/posts/search
Params:
  subreddit: str        # e.g. "studyAbroad"
  limit: int            # max 100 per request (paginate for more)
  after: str            # pagination cursor (post ID)
  fields: str           # comma-separated: "author,id,selftext,title,created_utc"
Response:
  { data: [ { author, id, selftext, title, created_utc }, ... ] }
```

#### Get all comments from a subreddit (for keyword matching)
```
GET /api/comments/search
Params:
  subreddit: str
  limit: int
  after: str
  fields: str           # "author,id,body,created_utc"
Response:
  { data: [ { author, id, body, created_utc }, ... ] }
```

#### Get all posts by a specific user (for scraping history)
```
GET /api/posts/search
Params:
  author: str           # Reddit username
  limit: int            # max 100 per request
  after: str            # pagination cursor
  fields: str           # "id,subreddit,title,selftext,score,created_utc,url"
Response:
  { data: [ { id, subreddit, title, selftext, score, created_utc, url }, ... ] }
```

#### Get all comments by a specific user (for scraping history)
```
GET /api/comments/search
Params:
  author: str
  limit: int
  after: str
  fields: str           # "id,subreddit,body,score,created_utc,link_id"
Response:
  { data: [ { id, subreddit, body, score, created_utc, link_id }, ... ] }
```

### Rate Limiting Strategy
- Default: 1 second sleep between requests
- Check `X-RateLimit-Remaining` header on every response
- If `X-RateLimit-Remaining` < 5: sleep 5 seconds before next request
- On HTTP 429 (rate limited): sleep 30 seconds and retry
- Max retries per request: 3

### Pagination Strategy
- ArcticShift returns max 100 results per request
- To get all results: keep requesting with `after` set to the last item's ID until response returns empty `data` array
- This pagination loop lives entirely inside `arctic_api.py`

---

## 5. Data Flow

```
User clicks "Start Identification"
        ↓
identifier.py calls arctic_api.py
        ↓
arctic_api.py paginates through ArcticShift API
        ↓
identifier.py applies filters (keyword match / one-time poster / random sample)
        ↓
Identified user list stored in Streamlit session state
        ↓
User clicks "Proceed to Scrape"
        ↓
scraper.py reads user list from session state
        ↓
For each user: arctic_api.py fetches all posts + comments
        ↓
scraper.py collects all records into a list
        ↓
exporter.py deduplicates by post_id and writes CSV
        ↓
CSV lands in /output folder
```

---

## 6. Background Processing Strategy

Streamlit runs in a single thread by default, which means long-running tasks (like scraping 500 users) would freeze the UI. We solve this with Python's built-in `threading` module — a way to run a task in the background while the main UI stays interactive.

```
Scrape job starts → launched in a background Thread
Main Streamlit thread → updates progress bar by reading shared state
Background thread → writes progress updates to a shared dict in session state
User can see live updates without the app freezing
```

Note: We use `threading` rather than `asyncio` here because Streamlit's session state works more predictably with threads. `asyncio` is reserved for the HTTP client layer inside `arctic_api.py`.

---

## 7. CSV Output Schema

Every CSV file has the same column structure. One row = one post or comment.

| Column | Type | Description |
|---|---|---|
| `username` | string | Reddit username |
| `control_group` | string | "primary_studyAbroad", "secondary_REU", or "secondary_college" |
| `source_subreddit` | string | Subreddit they were sampled from |
| `selection_reason` | string | "one_time_poster", "keyword_match", or "random_sample" |
| `post_id` | string | Unique Reddit ID |
| `post_type` | string | "post" or "comment" |
| `subreddit` | string | Subreddit where this post/comment appeared |
| `title` | string | Post title (empty for comments) |
| `body` | string | Post selftext or comment body |
| `score` | integer | Upvotes minus downvotes |
| `created_utc` | timestamp | UTC timestamp of when it was posted |
| `url` | string | Direct Reddit link |
| `is_deleted` | boolean | True if post was deleted/removed but archived by ArcticShift |

---

## 8. Key Dependencies

Listed in `requirements.txt`:

```
streamlit>=1.32.0       # Web UI framework
httpx>=0.27.0           # Async HTTP client for ArcticShift API calls
pandas>=2.0.0           # Data processing and CSV export
```

No other external dependencies needed. All other tools used (`threading`, `asyncio`, `time`, `json`, `os`, `datetime`) are part of Python's standard library — meaning they come pre-installed with Python and don't need to be pip-installed.

---

## 9. Setup Instructions (for lab members)

These will be expanded into a full README.md but the core steps are:

1. Clone or download the project folder
2. Open terminal, navigate to the project folder
3. Run: `pip3 install -r requirements.txt`
4. Run: `python3 -m streamlit run app.py`
5. Browser opens automatically at `http://localhost:8501`
6. No API keys, accounts, or additional configuration needed
