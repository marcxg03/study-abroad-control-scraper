# KNOWN_ISSUES.md
# Reddit Control Group Scraper

## How to use this file
Log bugs, limitations, and technical debt here as they are discovered during or after each slice. Include the slice where the issue was found, a description, severity, and whether it's been addressed.

**Severity levels:**
- 🔴 Critical — blocks core functionality
- 🟡 Medium — degrades experience but has a workaround
- 🟢 Low — minor issue, cosmetic, or edge case

---

## Pre-build Known Limitations

### KI-001: ArcticShift uptime not guaranteed
**Slice**: All slices involving arctic_api.py
**Severity**: 🟡 Medium
**Description**: ArcticShift is a community-maintained project with no SLA. If the API is down, scraping will fail entirely.
**Workaround**: Retry logic (MAX_RETRIES) handles brief outages. For extended outages, wait and retry the session.
**Status**: Open — by design, no fix planned

### KI-002: Very large subreddits may take a long time to paginate
**Slice**: Slice 2 (arctic_api.py), Slice 3 (identifier.py)
**Severity**: 🟡 Medium
**Description**: r/college is a large subreddit. Fetching all posts for user identification could take many minutes before we can apply the random sample filter.
**Workaround**: Consider fetching a large-but-not-exhaustive batch (e.g., 5000 posts) for random sampling rather than paginating fully through the entire subreddit.
**Status**: Open — to be evaluated after Slice 2 is built and tested

### KI-003: ArcticShift keyword search is limited
**Slice**: Slice 3 (identifier.py)
**Severity**: 🟡 Medium
**Description**: ArcticShift's full-text search only works within a specific author or subreddit context, and may be slow for large subreddits. We handle keyword matching client-side (in Python) after fetching posts — this is correct but means we must download more data than strictly necessary.
**Workaround**: None needed — client-side filtering is reliable, just slower.
**Status**: Open — by design

---

## Issues Found During Build
*Add entries here as they are discovered.*

### KI-004: System Python version is 3.9.6, spec requires 3.10+
**Slice**: Slice 1 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: The system `python3` resolves to 3.9.6. Current code works fine on 3.9 since no 3.10-only syntax is used. Risk arises only if later slices use features like `match/case` or `X | Y` union types.
**Workaround**: Avoid 3.10-only syntax in all slices. If a runtime error occurs citing Python version, install Python 3.10+ via Homebrew (`brew install python@3.10`) and relaunch with `python3.10 -m streamlit run app.py`.
**Status**: Open — deferred, monitor in later slices

### KI-005: No max_results cap in _paginate() — large subreddits may run indefinitely
**Slice**: Slice 2 (discovered during Claude Code verification)
**Severity**: 🟡 Medium
**Description**: arctic_api.py's internal _paginate() function has no upper limit on pages fetched. For large subreddits like r/college or prolific users, this could run for hours.
**Workaround**: Slice 3 (identifier.py) will pass a max_results ceiling into API calls for the user identification step. Full pagination is only needed during the post history scrape (Slice 4), where fetching everything is intentional.
**Status**: To be addressed in Slice 3

### KI-006: Shared created_utc timestamp may cause early pagination stop
**Slice**: Slice 2 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: ArcticShift uses created_utc as the pagination cursor. If multiple posts share the exact same timestamp, the seen-cursors guard may stop pagination early, missing some posts.
**Workaround**: Rare in practice. Monitor for unexpectedly low post counts during Slice 3 testing.
**Status**: Open — low priority, revisit if data gaps are observed

### KI-007: max_results truncates after fetching, not during pagination
**Slice**: Slice 3 (discovered during Claude Code verification)
**Severity**: 🟡 Medium
**Description**: The MAX_IDENTIFICATION_POSTS cap is applied after all pages are fetched, not as an early exit. For large subreddits like r/studyAbroad with years of history, identification may run for many minutes before results appear.
**Workaround**: The Streamlit UI (Slice 6) should surface a clear "Identifying users..." spinner so lab members know it's working. A true mid-pagination early exit would require modifying arctic_api.py — deferred.
**Status**: Open — partially mitigated by UI progress indicator in Slice 6

### KI-008: _is_bot() misses common Reddit bot patterns
**Slice**: Slice 3 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: Current bot filter only catches usernames ending in _bot or Bot, plus [deleted] and AutoModerator. Common bots like RemindMeBot, WikiTextBot, RepostSleuthBot would pass through and appear in user lists.
**Workaround**: Add a BOT_BLOCKLIST to config.py with known bot usernames. Claude Code can patch _is_bot() to check against it.
**Status**: Open — low priority, can be addressed as a Claude Code patch before Slice 6

### KI-009: identify_secondary_control() target_n has no default value
**Slice**: Slice 3 (discovered during Claude Code verification)
**Severity**: 🟡 Medium
**Description**: Unlike identify_primary_control(), the secondary function still requires target_n positionally. If Slice 6 UI calls it without target_n it will raise a TypeError.
**Workaround**: Must be fixed before Slice 6. Claude Code should patch the signature to target_n=None — the function body already handles None correctly.
**Status**: Fix required before Slice 6 — add to Slice 6 Claude Code debugging prompt

### KI-010: REQUEST_DELAY_SECONDS applied before first request unnecessarily
**Slice**: Slice 2 (discovered during timeout fix session)
**Severity**: 🟢 Low
**Description**: The 1-second delay fires before every request including the very first one, adding unnecessary latency at the start of every call chain.
**Workaround**: No impact on correctness — only adds ~1s per function call. Can be refactored in a future cleanup pass to sleep only between pages.
**Status**: Open — low priority, deferred

### KI-011: identifier.py post-hoc truncation now redundant
**Slice**: Slice 3 (discovered during Slice 2 timeout fix)
**Severity**: 🟢 Low  
**Description**: The records[:max_results] slice in identifier.py _call_arctic_api() is now a no-op since max_results is properly supported in arctic_api.py public functions.
**Workaround**: Not a bug — just dead code. Safe to remove in a future cleanup pass.
**Status**: Open — low priority, deferred

### KI-012: Double-write to progress["results"] 
**Slice**: Slice 4 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: scrape_users() sets progress["results"] inside the loop AND start_scrape_thread()'s _run() function sets it again after completion. Currently harmless (same value) but could confuse a Streamlit polling loop reading live progress.
**Workaround**: None needed for now. Remove one of the two assignments in a future cleanup pass.
**Status**: Open — low priority, deferred

### KI-013: No failed vs completed distinction in progress counter
**Slice**: Slice 4 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: progress["completed"] increments in the finally block regardless of success or failure. UI cannot distinguish "completed successfully" from "completed with error" without inspecting failed_users list separately.
**Workaround**: Slice 6 UI should check both progress["completed"] and len(progress["failed_users"]) when displaying status.
**Status**: Open — to be handled in Slice 6 UI design

### KI-014: No per-user post cap — prolific users fetch unlimited records
**Slice**: Slice 4 (discovered during Claude Code verification)
**Severity**: 🟡 Medium
**Description**: max_results=None is passed for full history scrapes, meaning a very prolific user could take many minutes and consume significant memory.
**Workaround**: Consider adding MAX_POSTS_PER_USER to config.py before Slice 6. For research purposes, full history is likely desired, so this is a judgment call.
**Status**: Open — review before Slice 6

### KI-015: No top-level "error" status set for unrecoverable exceptions in scrape_users()
**Slice**: Slice 4 (discovered during test fix session)
**Severity**: 🟢 Low
**Description**: progress["status"] = "error" is never set. Per-user failures are caught and appended to failed_users, but if scrape_users() itself crashes unexpectedly, status stays as "running" forever.
**Workaround**: Slice 6 UI should implement a timeout check — if thread is no longer alive but status is still "running", display an error state.
**Status**: Open — low priority, deferred to Slice 6

### KI-016: None values normalized to empty string in CSV output
**Slice**: Slice 5 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: title=None for comments becomes "" in the CSV rather than NaN. R/Python analysis using pd.isna(df.title) will see empty string, not NaN.
**Workaround**: Document this convention in README — filter on df.title == "" to find comments.
**Status**: Open — low priority, document in README

### KI-017: Global deduplication before group split may silently drop cross-group records
**Slice**: Slice 5 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: post_id deduplication runs globally before splitting by group. If the same post_id appears in two groups (shouldn't happen by design but possible if identifier logic overlaps), one record is silently dropped.
**Workaround**: By design, users shouldn't overlap across groups. KI-008 bot blocklist and deduplication in identifier.py minimize this risk.
**Status**: Open — low priority

### KI-018: write_run_log calls datetime.now() twice
**Slice**: Slice 5 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: Filename timestamp and log body timestamp are captured separately — could differ by one second under load.
**Workaround**: Cosmetic only — no functional impact.
**Status**: Open — low priority, cleanup candidate

### KI-019: Unknown control_group values silently discarded
**Slice**: Slice 5 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: Records with a control_group key not matching known group names are silently dropped with no warning or log entry.
**Workaround**: Unlikely in practice since groups are hardcoded. If data looks short, check for typos in control_group values.
**Status**: Open — low priority

### KI-020: Page main() calls guarded by if __name__ == "__main__"
**Slice**: Slice 6 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: Works correctly with current Streamlit execution model but could silently break if Streamlit's module import path changes.
**Workaround**: None needed currently.
**Status**: Open — low priority

### KI-021: time.sleep(2) on main thread during progress polling
**Slice**: Slice 6 (discovered during Claude Code verification)
**Severity**: 🟢 Low
**Description**: render_progress_section() calls time.sleep(2) on the main thread, briefly freezing the UI on each poll cycle while scraping runs.
**Workaround**: Acceptable for a single-user local tool. No fix needed.
**Status**: Open — by design, acceptable for local use

### KI-022: reset_workflow_state() clears identified users for ALL groups
**Slice**: Slice 6 (discovered during Claude Code verification)
**Severity**: 🟡 Medium
**Description**: Clicking "Identify Users" on any page resets identified_users for all groups. Running group A then group B without scraping A first loses group A's user list.
**Workaround**: Always scrape each group immediately after identifying before moving to the next group. Document this in README.
**Status**: Open — document in README as workflow guidance

### KI-023: Shared progress dict overwritten by sequential multi-group scrapes
**Slice**: Slice 6 (discovered during Claude Code verification)
**Severity**: 🟡 Medium
**Description**: If scraping is run on page 1 then page 2 sequentially, page 2's scrape overwrites page 1's results in session state.
**Workaround**: Complete the full workflow (identify → scrape → download CSV) for one group before starting the next. Document in README.
**Status**: Open — document in README as workflow guidance
