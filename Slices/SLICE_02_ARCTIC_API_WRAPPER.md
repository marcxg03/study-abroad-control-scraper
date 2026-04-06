# SLICE_02_ARCTIC_API_WRAPPER.md
# Reddit Control Group Scraper

## Goal
Build the `arctic_api.py` module — the single layer through which all ArcticShift API calls are made. This module handles HTTP requests, pagination, rate limiting, and retries. No other module should ever call the ArcticShift API directly.

## Acceptance Criteria
1. `arctic_api.py` can fetch all posts from a given subreddit, paginating automatically until all results are returned
2. `arctic_api.py` can fetch all comments from a given subreddit with the same pagination logic
3. `arctic_api.py` can fetch all posts by a specific username across all subreddits
4. `arctic_api.py` can fetch all comments by a specific username across all subreddits
5. Every request waits `REQUEST_DELAY_SECONDS` (from config.py) between calls
6. If `X-RateLimit-Remaining` header is below 5, the module sleeps 5 seconds before the next request
7. On HTTP 429 response, the module sleeps 30 seconds and retries
8. Failed requests retry up to `MAX_RETRIES` times before raising an exception
9. All functions are testable independently via a simple Python script (no Streamlit needed)

## Files to Create or Modify
- `modules/arctic_api.py` — full implementation (replaces stub from Slice 1)

## Component Contracts

### Functions in `arctic_api.py`

```python
def get_subreddit_posts(
    subreddit: str,
    fields: list[str] = ["author", "id", "title", "selftext", "created_utc"],
    limit_per_request: int = 100
) -> list[dict]:
    """
    Fetches all posts from a given subreddit.
    Paginates automatically until no more results are returned.
    Returns a flat list of post dicts.
    """

def get_subreddit_comments(
    subreddit: str,
    fields: list[str] = ["author", "id", "body", "created_utc"],
    limit_per_request: int = 100
) -> list[dict]:
    """
    Fetches all comments from a given subreddit.
    Paginates automatically until no more results are returned.
    Returns a flat list of comment dicts.
    """

def get_user_posts(
    username: str,
    fields: list[str] = ["id", "subreddit", "title", "selftext", "score", "created_utc", "url"],
    limit_per_request: int = 100
) -> list[dict]:
    """
    Fetches complete post history for a given username across all subreddits.
    Paginates automatically.
    Returns a flat list of post dicts.
    """

def get_user_comments(
    username: str,
    fields: list[str] = ["id", "subreddit", "body", "score", "created_utc", "link_id"],
    limit_per_request: int = 100
) -> list[dict]:
    """
    Fetches complete comment history for a given username across all subreddits.
    Paginates automatically.
    Returns a flat list of comment dicts.
    """
```

### Internal helper (private, not called by other modules)
```python
def _make_request(endpoint: str, params: dict) -> dict:
    """
    Makes a single GET request to the ArcticShift API.
    Handles rate limit headers, 429 responses, and retries.
    Returns parsed JSON response dict.
    Raises Exception after MAX_RETRIES failures.
    """
```

## Edge Cases to Handle
- Empty subreddit: if the subreddit has no posts, return an empty list — do not raise an error
- Deleted authors: ArcticShift may return posts where `author` is `"[deleted]"` — include these, do not filter them out
- Missing fields: if a requested field is absent from a response item, fill it with `None` — do not crash
- Pagination end: stop paginating when the API returns an empty `data` array
- Network timeout: treat as a failed request and apply retry logic

## Test Cases
Run these manually in a Python script after Codex generates the module:

```python
# Test 1: fetch first page of r/studyAbroad posts (small subreddit — won't take long)
from modules.arctic_api import get_subreddit_posts
posts = get_subreddit_posts("studyAbroad", limit_per_request=10)
assert len(posts) > 0
assert "author" in posts[0]
print(f"✅ Test 1 passed — {len(posts)} posts fetched")

# Test 2: fetch posts for a known active user
from modules.arctic_api import get_user_posts
posts = get_user_posts("spez", limit_per_request=10)
assert len(posts) > 0
print(f"✅ Test 2 passed — {len(posts)} posts fetched for u/spez")

# Test 3: fetch comments for the same user
from modules.arctic_api import get_user_comments
comments = get_user_comments("spez", limit_per_request=10)
assert len(comments) > 0
print(f"✅ Test 3 passed — {len(comments)} comments fetched for u/spez")
```

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Reddit Control Group Scraper" for a psychology research lab. The app fetches Reddit data via the ArcticShift public API (base URL: https://arctic-shift.photon-reddit.com). The project uses Python 3.10+, httpx (for HTTP requests), and pandas. The scaffold and config.py are already in place from Slice 1.

TASK:
Implement modules/arctic_api.py — the sole module responsible for all HTTP communication with the ArcticShift API. This is Slice 2 of 6.

FILES TO CREATE:
- modules/arctic_api.py — full implementation (replaces the stub from Slice 1)

CONSTRAINTS:
- Use httpx (synchronous client, not async) for all HTTP calls — Streamlit threading works more reliably with synchronous httpx
- Import all config values from config.py — do not hardcode URLs, delays, or retry counts
- All four public functions must match these exact signatures:
    get_subreddit_posts(subreddit, fields, limit_per_request) -> list[dict]
    get_subreddit_comments(subreddit, fields, limit_per_request) -> list[dict]
    get_user_posts(username, fields, limit_per_request) -> list[dict]
    get_user_comments(username, fields, limit_per_request) -> list[dict]
- One private helper _make_request(endpoint, params) -> dict handles all HTTP logic
- Pagination: use "after" param set to the last item's ID; stop when data array is empty
- Rate limiting: sleep REQUEST_DELAY_SECONDS between every request
- If X-RateLimit-Remaining header < 5: sleep 5 seconds
- On HTTP 429: sleep 30 seconds and retry
- Max retries: MAX_RETRIES from config.py
- Missing response fields should be filled with None, never raise KeyError
- Do not import streamlit — this module must be usable without Streamlit running

ACCEPTANCE CRITERIA:
1. get_subreddit_posts("studyAbroad", limit_per_request=10) returns a non-empty list of dicts
2. get_user_posts("spez", limit_per_request=10) returns a non-empty list of dicts
3. get_user_comments("spez", limit_per_request=10) returns a non-empty list of dicts
4. All functions paginate correctly — they keep fetching until API returns empty data array
5. Rate limit logic is applied on every request
6. No hardcoded values — everything comes from config.py

DO NOT:
- Implement any filtering, keyword matching, or CSV logic — that belongs in later slices
- Use async/await — use synchronous httpx only
- Modify any files outside modules/arctic_api.py
- Add Streamlit imports

OUTPUT:
Write the complete implementation for modules/arctic_api.py. After writing, list any assumptions you made.
```

---

## Claude Code Debugging Prompt

```
CONTEXT:
I am building a local Streamlit app called "Reddit Control Group Scraper." Slice 2 (ArcticShift API wrapper) was just generated by Codex. The module lives at modules/arctic_api.py and makes HTTP calls to https://arctic-shift.photon-reddit.com using the httpx library.

CURRENT PROBLEM:
[Paste exact error message or describe what isn't working]

RELEVANT FILES:
- modules/arctic_api.py
- config.py

WHAT CODEX BUILT:
Four public functions for fetching subreddit posts, subreddit comments, user posts, and user comments from ArcticShift. One private _make_request helper handles HTTP, retries, and rate limiting.

CONSTRAINTS:
- Use synchronous httpx only — no async/await
- All config values must come from config.py — no hardcoding
- Do not add Streamlit imports
- Do not modify any files outside modules/arctic_api.py and config.py
- Pagination must use "after" param with the last item's ID
- Missing response fields must return None, not raise exceptions

ACCEPTANCE CRITERIA:
1. get_subreddit_posts("studyAbroad", limit_per_request=10) returns non-empty list
2. get_user_posts("spez", limit_per_request=10) returns non-empty list
3. get_user_comments("spez", limit_per_request=10) returns non-empty list
4. Rate limit headers are checked on every response
5. Retries work correctly on failure

DO NOT:
- Rewrite functions that are already working
- Add filtering or CSV logic
- Switch to async

OUTPUT:
Fix the problem described above. Summarize what was changed, why, and list any follow-up issues for the next Claude Code session.
```
