# SLICE_04_POST_HISTORY_SCRAPER.md
# Reddit Control Group Scraper

## Goal
Build the `scraper.py` module, which takes a list of identified users and fetches their complete Reddit post and comment history across all subreddits via ArcticShift. Scraping runs in a background thread so the Streamlit UI stays responsive.

## Acceptance Criteria
1. `scrape_users()` accepts a list of User Record dicts and returns a list of Post Record dicts
2. For each user, both posts AND comments are fetched from across all subreddits
3. Each returned Post Record includes the `is_deleted` flag — True if the post body is `[removed]` or `[deleted]`
4. Scraping runs in a background thread — the function does not block the calling thread
5. A shared progress dict is updated in real time: `{"completed": int, "total": int, "current_user": str, "status": str}`
6. Failed users (after MAX_RETRIES) are logged to the progress dict under `"failed_users"` and skipped — scraping continues
7. A cancel flag can be passed in to stop scraping mid-run cleanly
8. The function is testable independently via a plain Python script

## Files to Create or Modify
- `modules/scraper.py` — full implementation (replaces stub from Slice 1)

## Component Contracts

### Functions in `scraper.py`

```python
def scrape_users(
    users: list[dict],
    progress: dict,
    cancel_flag: list[bool]
) -> list[dict]:
    """
    Fetches complete post + comment history for each user in the list.
    Runs synchronously — caller is responsible for running in a thread.
    
    users: list of User Record dicts (output of identifier.py)
    progress: shared dict updated in real time with keys:
              completed (int), total (int), current_user (str),
              status (str), failed_users (list[str])
    cancel_flag: single-element list [False] — set to [True] to stop scraping
    
    Returns a flat list of Post Record dicts.
    """

def start_scrape_thread(
    users: list[dict],
    progress: dict,
    cancel_flag: list[bool]
) -> threading.Thread:
    """
    Launches scrape_users() in a background thread.
    Returns the thread object so the caller can check thread.is_alive().
    """
```

### Post Record dict schema (output)
```python
{
    "username": str,
    "control_group": str,
    "source_subreddit": str,
    "selection_reason": str,
    "post_id": str,
    "post_type": str,           # "post" or "comment"
    "subreddit": str,
    "title": str,               # None for comments
    "body": str,
    "score": int,
    "created_utc": str,         # ISO format UTC timestamp
    "url": str,
    "is_deleted": bool
}
```

### Progress dict structure
```python
{
    "completed": 0,             # number of users fully scraped
    "total": len(users),        # total users to scrape
    "current_user": "",         # username currently being scraped
    "status": "running",        # "running", "done", "cancelled", "error"
    "failed_users": []          # usernames that failed after all retries
}
```

### `is_deleted` detection logic
A post or comment is marked `is_deleted = True` if:
- `body` field equals `"[removed]"` or `"[deleted]"` (exact match, case-insensitive)
- OR `author` field equals `"[deleted]"`

## Edge Cases to Handle
- User has zero posts: record nothing for them, mark as completed, continue
- User has posts but zero comments (or vice versa): include whichever exist
- `cancel_flag[0]` becomes True mid-scrape: stop after finishing the current user, set `progress["status"] = "cancelled"`
- A single user fails all retries: add to `failed_users`, set their status to failed in progress, continue to next user
- `created_utc` from ArcticShift is a Unix timestamp (integer seconds): convert to ISO format string

## Test Cases

```python
import threading
from modules.identifier import identify_secondary_control
from modules.scraper import scrape_users, start_scrape_thread

# Test 1: Scrape 2 users synchronously
users = identify_secondary_control("REU", "secondary_REU", target_n=2)
progress = {"completed": 0, "total": 2, "current_user": "", "status": "running", "failed_users": []}
cancel_flag = [False]

posts = scrape_users(users, progress, cancel_flag)
assert len(posts) > 0
assert all("post_id" in p for p in posts)
assert all("is_deleted" in p for p in posts)
assert all(p["post_type"] in ["post", "comment"] for p in posts)
assert progress["completed"] == 2
assert progress["status"] == "done"
print(f"✅ Test 1 passed — {len(posts)} posts scraped for 2 users")

# Test 2: Cancel flag stops scraping
users = identify_secondary_control("college", "secondary_college", target_n=5)
progress = {"completed": 0, "total": 5, "current_user": "", "status": "running", "failed_users": []}
cancel_flag = [False]

def cancel_after_first():
    import time
    time.sleep(2)
    cancel_flag[0] = True

t = threading.Thread(target=cancel_after_first)
t.start()
posts = scrape_users(users, progress, cancel_flag)
assert progress["status"] == "cancelled"
assert progress["completed"] < 5
print(f"✅ Test 2 passed — scrape cancelled after {progress['completed']} users")
```

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Reddit Control Group Scraper" for a psychology research lab. The app scrapes Reddit user history via the ArcticShift API. Slices 1-3 are complete: the scaffold, API wrapper (arctic_api.py), and user identifier (identifier.py) are all working. arctic_api.py provides get_user_posts(username) and get_user_comments(username).

TASK:
Implement modules/scraper.py — the module that takes a list of identified users and fetches their complete Reddit history. This is Slice 4 of 6.

FILES TO CREATE:
- modules/scraper.py — full implementation (replaces stub from Slice 1)

CONSTRAINTS:
- Import from modules.arctic_api only — do not make direct HTTP calls
- Import config values from config.py
- Two public functions with exact signatures:
    scrape_users(users, progress, cancel_flag) -> list[dict]
    start_scrape_thread(users, progress, cancel_flag) -> threading.Thread
- scrape_users() runs synchronously — threading is handled by start_scrape_thread()
- start_scrape_thread() launches scrape_users() in a daemon=True background thread
- Progress dict must be updated after each user completes
- cancel_flag is a single-element list [False] — check cancel_flag[0] between users
- If cancel_flag[0] is True: stop after current user, set progress["status"] = "cancelled"
- is_deleted = True if body is "[removed]" or "[deleted]" (case-insensitive) OR author is "[deleted]"
- created_utc from ArcticShift is a Unix integer — convert to ISO format UTC string
- Post Record dict must have exactly these keys:
    username, control_group, source_subreddit, selection_reason,
    post_id, post_type, subreddit, title, body, score, created_utc, url, is_deleted
- title is None for comments
- url for comments: construct as "https://reddit.com" + permalink if available, else None
- Do not import streamlit

ACCEPTANCE CRITERIA:
1. scrape_users() returns a non-empty list of Post Record dicts for a valid user list
2. Both posts and comments are included for each user
3. progress dict is updated in real time (completed increments after each user)
4. cancel_flag stops scraping cleanly
5. Failed users after MAX_RETRIES are added to progress["failed_users"] and skipped
6. is_deleted is correctly set

DO NOT:
- Write CSV files — that belongs in Slice 5
- Add Streamlit imports
- Modify arctic_api.py or identifier.py
- Use async/await

OUTPUT:
Write the complete implementation for modules/scraper.py. After writing, list any assumptions you made.
```

---

## Claude Code Debugging Prompt

```
CONTEXT:
I am building a local Streamlit app called "Reddit Control Group Scraper." Slice 4 (post history scraper) was just generated by Codex. The module lives at modules/scraper.py and depends on modules/arctic_api.py (working) and config.py.

CURRENT PROBLEM:
[Paste exact error message or describe what isn't working]

RELEVANT FILES:
- modules/scraper.py
- modules/arctic_api.py
- config.py

WHAT CODEX BUILT:
scrape_users() fetches full post + comment history for a list of users via arctic_api.py. start_scrape_thread() launches it in a background thread. Progress is tracked via a shared dict. Cancel flag stops scraping cleanly between users.

CONSTRAINTS:
- Do not make direct HTTP calls in scraper.py — must use arctic_api functions
- Do not add Streamlit imports
- Do not modify arctic_api.py unless bug is provably caused there
- Post Record schema must stay exactly as specified
- Threading must use daemon=True threads
- cancel_flag must be a single-element list pattern

ACCEPTANCE CRITERIA:
1. scrape_users() returns Post Record dicts with correct schema
2. progress dict updates after each user
3. cancel_flag works correctly
4. is_deleted flag is set correctly
5. Both posts and comments included per user

DO NOT:
- Add CSV writing logic
- Change threading approach
- Rewrite working functions

OUTPUT:
Fix the problem described above. Summarize what was changed, why, and list any follow-up issues for the next Claude Code session.
```
