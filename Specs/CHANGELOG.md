# CHANGELOG.md
# Reddit Control Group Scraper

## How to use this file
After each slice is built and verified, add an entry here describing what was completed and any deviations from the original spec. This file is your running record of what the app can actually do at any point in time.

---

## [Slice 1 — Project Scaffold] ✅ COMPLETE

### What was built
- Full folder structure as specified in ARCHITECTURE.md
- `config.py` with all hardcoded values: API base URL, group definitions, cancellation keywords, defaults
- `app.py` home screen with three group cards (Primary Control, Secondary Control A/B)
- `requirements.txt` pinned to: streamlit==1.50.0, httpx, pandas
- `README.md` with setup instructions
- Importable stubs for all four modules: arctic_api.py, identifier.py, scraper.py, exporter.py
- Three title-only Streamlit pages for each group

### Verification results
- All four acceptance criteria passed cleanly via Claude Code
- `from modules import identifier, scraper, exporter, arctic_api` — ✅ no errors
- `config.ARCTIC_SHIFT_BASE_URL` — ✅ correct
- `/output` and `/logs` auto-created on startup — ✅ confirmed
- Streamlit healthz check — ✅ returns ok

### Deviations from spec
- None

### Known issues surfaced
- KI-004: System Python is 3.9.6 (spec says 3.10+) — deferred, low risk

---

## [Slice 2 — ArcticShift API Wrapper] ✅ COMPLETE

### What was built
- Full implementation of modules/arctic_api.py
- Four public functions: get_subreddit_posts(), get_subreddit_comments(), get_user_posts(), get_user_comments()
- Private _make_request() and _paginate() helpers handling all HTTP logic
- Rate limiting, 429 retry, configurable delay — all sourced from config.py
- Missing fields filled with None instead of raising KeyError

### Verification results
- First page fetches confirmed working for subreddit posts, user posts, user comments
- Pagination verified correct with after=<created_utc> cursor

### Deviations from spec
- Pagination cursor uses created_utc (Unix timestamp) not item ID — ArcticShift API requires this. Spec assumed ID-based pagination; Claude Code caught and corrected this.

### Known issues surfaced
- KI-005: No max_results cap in _paginate() — RESOLVED in follow-up fix
- KI-006: Shared created_utc timestamps may cause early pagination stop — low priority, still open

### Follow-up fix applied (post Claude Code session)
- Added REQUEST_TIMEOUT_SECONDS = 30.0 and MAX_RESULTS_PER_CALL = 500 to config.py
- httpx.Client() now receives timeout=REQUEST_TIMEOUT_SECONDS — fixes indefinite hang
- _paginate() gains max_results early-exit parameter — prevents 4+ hour runs on large subreddits
- All four public functions expose max_results parameter — identifier.py wires through correctly

## [Slice 3 — User Identification] ✅ COMPLETE

### What was built
- Full implementation of modules/identifier.py
- identify_primary_control(): keyword + one-time poster filtering for r/studyAbroad
- identify_secondary_control(): random sampling for r/REU and r/college
- Private helpers: _is_bot(), _keyword_match(), _deduplicate_users()
- MAX_IDENTIFICATION_POSTS = 5000 added to config.py
- Compatibility layer for max_results — caps locally if API wrapper does not yet support it

### Verification results
- All four test cases passed after Claude Code fixes
- Pagination confirmed working beyond 100 posts (created_utc cursor fix)

### Deviations from spec
- One-time poster defined as one total contribution (posts + comments combined) within the fetched pool, not posts only
- max_results implemented as a local post-fetch cap rather than a mid-pagination stop (Codex could not modify arctic_api.py per slice constraints)

### Bugs caught by Claude Code
1. Missing default for keywords parameter — caused TypeError when calling identify_primary_control(target_n=10)
2. "body" is not a valid ArcticShift field for posts — must use "selftext"; would have caused 400 errors
3. created_utc missing from field lists — pagination silently capped at 100 users per run

### Known issues surfaced
- KI-007: max_results truncates after fetching, not during — large subreddits still fetch fully before cap applies
- KI-008: _is_bot() misses common bot patterns like RemindMeBot, WikiTextBot
- KI-009: identify_secondary_control target_n has no default — may error if called without it from UI

## [Slice 4 — Post History Scraper] ✅ COMPLETE

### What was built
- Full implementation of modules/scraper.py
- scrape_users(): fetches complete post + comment history for each user via arctic_api
- start_scrape_thread(): launches scrape in a daemon background thread
- Post Record schema normalized correctly: unix timestamps → ISO strings, is_deleted flag, comment URLs from permalink
- progress dict updated in real time, cancel_flag respected between users
- Failed users caught and logged to progress["failed_users"]

### Verification results
- All ACs passed live with real data
- End-to-end smoke test: 1,050 posts + 4,941 comments = 5,991 records confirmed correct schema
- progress dict, cancel_flag, is_deleted all verified working

### Deviations from spec
- fields=None passed to arctic_api calls (fetches all fields) rather than explicit field list — correct behavior for full history scrape
- Scrape result stored on progress["results"] to allow thread output access without changing function signatures

### Bugs caught by Claude Code
1. "permalink" rejected as a field parameter by ArcticShift (400 error) — caused every scrape call to fail. Fixed by dropping fields filter entirely (fields=None)

### Known issues surfaced
- KI-012: Double-write to progress["results"] — harmless but could confuse Streamlit polling loop
- KI-013: No failed vs completed distinction in progress counter
- KI-014: No per-user post cap — prolific users fetch unlimited records

## [Slice 5 — CSV Exporter] ✅ COMPLETE

### What was built
- Full implementation of modules/exporter.py
- export_to_csv(): deduplicates by post_id, splits by control_group, writes three named CSVs
- write_run_log(): writes timestamped plain-text summary log
- Empty groups produce header-only files — no groups skipped
- Column order matches spec exactly

### Verification results
- All five ACs passed with zero fixes needed — no Claude Code changes required
- Codex output was correct on first generation

### Deviations from spec
- Summary dict uses rows_per_group and filepath_per_group as keys (minor naming variation from spec)

### Known issues surfaced
- KI-016: None values normalized to empty string — title=None for comments becomes  not NaN
- KI-017: Deduplication is global before group split — cross-group post_id collision would silently drop a record
- KI-018: write_run_log calls datetime.now() twice — filename and log line could differ by one second
- KI-019: Unknown control_group values silently discarded with no warning

## [Slice 6 — Streamlit UI] ✅ COMPLETE

### What was built
- Full Streamlit UI across app.py and three group pages
- Home screen with three group cards linking to workflow pages
- Each page: configuration → identification results table → background scrape with progress bar + cancel → CSV download buttons
- Primary Control page: editable keyword list pre-filled from config
- All three pages: sample size input defaulting to DEFAULT_SAMPLE_SIZE
- KI-008 fix: BOT_BLOCKLIST added to config.py, _is_bot() updated to check it
- KI-009 fix: identify_secondary_control() now accepts target_n=None
- KI-008 fix: MAX_IDENTIFICATION_POSTS confirmed in config.py
- Export triggered automatically when scrape thread finishes
- All three CSVs available as download buttons after scrape completes
- Failed users shown in expandable warning section
- No raw tracebacks — all errors shown via st.error()

### Verification results
- All six ACs passed with zero fixes needed
- App launches, all pages return HTTP 200
- Background scrape, cancel, and download buttons all verified

### Deviations from spec
- Three download buttons shown on every page for all groups (including header-only files for groups not scraped in that run) — simpler than per-group conditional display
- Run All Groups kept as guided placeholder — session/thread model supports one active workflow at a time
- Export triggered automatically on scrape completion rather than requiring a manual button click

### Known issues surfaced
- KI-020: Page main() calls guarded by if __name__ == __main__ — works correctly but fragile
- KI-021: time.sleep(2) on main thread during progress polling — UI freezes briefly each poll cycle
- KI-022: reset_workflow_state() clears identified_users for ALL groups — running group A then B loses group A users if not scraped first
- KI-023: Shared progress dict overwritten if scraping run on multiple pages sequentially

## [Slice 6 — UI Polish] Post-launch improvements

### Changes made
- Added st.expander() help tooltips to all three group pages — one under each of: Configuration, Results, Scraping/Export sections
- Expanders collapsed by default, plain English explanations for non-technical lab members
- Replaced multi-group download buttons with single per-group download button on each page:
  - Primary Control page → primary_control_studyAbroad.csv only
  - Secondary Control A page → secondary_control_REU.csv only
  - Secondary Control B page → secondary_control_college.csv only
- Removed unused DOWNLOAD_GROUPS, DOWNLOAD_LABELS, DOWNLOAD_FILE_NAMES constants from all three page files

### Verified working
- End-to-end manual test completed: identification → scraping → CSV download all functional
- CSV output confirmed correct (blank body entries expected — posts with no text or deleted content)
