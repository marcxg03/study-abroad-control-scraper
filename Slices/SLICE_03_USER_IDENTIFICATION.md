# SLICE_03_USER_IDENTIFICATION.md
# Reddit Control Group Scraper

## Goal
Build the `identifier.py` module, which applies filtering logic to raw ArcticShift data to produce a clean, deduplicated list of users for each of the three control groups.

## Acceptance Criteria
1. `identify_primary_control()` returns users from r/studyAbroad who either posted exactly once OR whose posts/comments contain at least one cancellation keyword (case-insensitive)
2. `identify_secondary_control()` returns a random sample of unique users from a given subreddit (used for both r/REU and r/college)
3. All returned user lists are deduplicated — no username appears twice
4. Bots and deleted accounts are filtered out (usernames: `[deleted]`, `AutoModerator`, usernames ending in `_bot` or `Bot`)
5. Each returned user is represented as a dict matching the User Record schema from the Master Spec
6. Sample size is controlled by the `target_n` parameter, defaulting to `DEFAULT_SAMPLE_SIZE` from config.py
7. Functions work independently of Streamlit — testable via plain Python script

## Files to Create or Modify
- `modules/identifier.py` — full implementation (replaces stub from Slice 1)

## Component Contracts

### Functions in `identifier.py`

```python
def identify_primary_control(
    keywords: list[str] = None,
    target_n: int = None
) -> list[dict]:
    """
    Identifies r/studyAbroad users who either:
    - Posted exactly once in the subreddit (one_time_poster), OR
    - Mentioned a cancellation keyword in any post or comment (keyword_match)
    
    keywords: list of cancellation keywords to match against (defaults to CANCELLATION_KEYWORDS from config)
    target_n: max number of users to return (defaults to DEFAULT_SAMPLE_SIZE from config)
    
    Returns a list of User Record dicts.
    """

def identify_secondary_control(
    subreddit: str,
    group_key: str,
    target_n: int = None
) -> list[dict]:
    """
    Returns a random sample of unique, non-bot users from the given subreddit.
    
    subreddit: subreddit name (e.g. "REU" or "college")
    group_key: control group identifier (e.g. "secondary_REU")
    target_n: max number of users to return (defaults to DEFAULT_SAMPLE_SIZE from config)
    
    Returns a list of User Record dicts.
    """
```

### User Record dict schema (output of both functions)
```python
{
    "username": str,
    "source_subreddit": str,
    "control_group": str,           # "primary_studyAbroad", "secondary_REU", or "secondary_college"
    "selection_reason": str,        # "one_time_poster", "keyword_match", or "random_sample"
    "identified_at": str            # ISO format UTC timestamp e.g. "2024-03-15T10:30:00Z"
}
```

### Internal helpers (private)
```python
def _is_bot(username: str) -> bool:
    """Returns True if the username is a known bot or deleted account."""

def _keyword_match(text: str, keywords: list[str]) -> bool:
    """Returns True if any keyword appears in text (case-insensitive)."""

def _deduplicate_users(users: list[dict]) -> list[dict]:
    """Removes duplicate usernames, keeping the first occurrence."""
```

## Edge Cases to Handle
- A user who is both a one-time poster AND matches a keyword: record them once with `selection_reason = "keyword_match"` (keyword match takes priority)
- If `identify_primary_control()` finds fewer than `target_n` users after filtering: return however many were found — do not pad or error
- If `identify_secondary_control()` pulls more users than `target_n` after deduplication: randomly sample down to exactly `target_n`
- Keywords must match whole substrings case-insensitively — "Not Going" and "not going" must both match
- Usernames that are `None` or empty string: skip silently

## Test Cases

```python
# Test 1: Primary control returns user dicts with correct schema
from modules.identifier import identify_primary_control
users = identify_primary_control(target_n=10)
assert len(users) > 0
assert all("username" in u for u in users)
assert all("selection_reason" in u for u in users)
assert all(u["selection_reason"] in ["one_time_poster", "keyword_match"] for u in users)
assert all(u["control_group"] == "primary_studyAbroad" for u in users)
print(f"✅ Test 1 passed — {len(users)} primary control users identified")

# Test 2: No duplicate usernames
usernames = [u["username"] for u in users]
assert len(usernames) == len(set(usernames))
print("✅ Test 2 passed — no duplicate usernames")

# Test 3: Secondary control (REU)
from modules.identifier import identify_secondary_control
reu_users = identify_secondary_control("REU", "secondary_REU", target_n=10)
assert len(reu_users) > 0
assert all(u["selection_reason"] == "random_sample" for u in reu_users)
assert all(u["control_group"] == "secondary_REU" for u in reu_users)
print(f"✅ Test 3 passed — {len(reu_users)} REU users identified")

# Test 4: Bot filtering
from modules.identifier import _is_bot
assert _is_bot("[deleted]") == True
assert _is_bot("AutoModerator") == True
assert _is_bot("reddit_bot") == True
assert _is_bot("regular_user") == False
print("✅ Test 4 passed — bot filtering works")
```

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Reddit Control Group Scraper" for a psychology research lab. The app identifies Reddit users across three control groups using the ArcticShift API. Slices 1 (scaffold) and 2 (API wrapper) are complete. The arctic_api.py module is working and provides: get_subreddit_posts(), get_subreddit_comments(), get_user_posts(), get_user_comments().

TASK:
Implement modules/identifier.py — the module that applies filtering logic to raw ArcticShift data to produce clean user lists for each control group. This is Slice 3 of 6.

FILES TO CREATE:
- modules/identifier.py — full implementation (replaces stub from Slice 1)

CONSTRAINTS:
- Import from modules.arctic_api — do not make any direct HTTP calls
- Pass a max_results cap when calling arctic_api functions during identification — do NOT paginate exhaustively through large subreddits. Recommended cap: 5000 posts for r/college and r/REU, full pagination acceptable for r/studyAbroad (smaller subreddit). Implement this as a MAX_IDENTIFICATION_POSTS constant in config.py (default: 5000).
- Import all config values from config.py (CANCELLATION_KEYWORDS, DEFAULT_SAMPLE_SIZE, GROUPS)
- Two public functions with these exact signatures:
    identify_primary_control(keywords, target_n) -> list[dict]
    identify_secondary_control(subreddit, group_key, target_n) -> list[dict]
- Three private helpers:
    _is_bot(username) -> bool
    _keyword_match(text, keywords) -> bool
    _deduplicate_users(users) -> list[dict]
- User Record dict must have exactly these keys:
    username, source_subreddit, control_group, selection_reason, identified_at
- Bot filter must catch: "[deleted]", "AutoModerator", any username ending in "_bot" or "Bot"
- Keyword matching must be case-insensitive substring matching
- If a user is both a one-time poster and a keyword match, use selection_reason = "keyword_match"
- Add MAX_IDENTIFICATION_POSTS = 5000 to config.py — use this as the fetch ceiling when calling arctic_api functions during identification (prevents infinite pagination on large subreddits like r/college)
- Pass max_results=config.MAX_IDENTIFICATION_POSTS to all arctic_api calls inside identifier.py
- Full exhaustive pagination is NOT needed here — we just need enough posts to sample from
- Use Python's random.sample() for random sampling in identify_secondary_control()
- identified_at must be a UTC ISO format timestamp string
- Do not import streamlit

ACCEPTANCE CRITERIA:
1. identify_primary_control(target_n=10) returns a non-empty list of User Record dicts
2. All returned users have correct control_group and selection_reason values
3. No duplicate usernames in any returned list
4. Bots and deleted accounts are excluded
5. identify_secondary_control("REU", "secondary_REU", target_n=10) returns random_sample users
6. Keyword matching is case-insensitive

DO NOT:
- Make direct HTTP calls — use arctic_api functions only
- Implement any CSV writing or Streamlit UI
- Modify files outside modules/identifier.py
- Hardcode any keywords or subreddit names

OUTPUT:
Write the complete implementation for modules/identifier.py. After writing, list any assumptions you made.
```

---

## Claude Code Debugging Prompt

```
CONTEXT:
I am building a local Streamlit app called "Reddit Control Group Scraper." Slice 3 (user identification) was just generated by Codex. The module lives at modules/identifier.py and depends on modules/arctic_api.py (already working from Slice 2) and config.py.

CURRENT PROBLEM:
[Paste exact error message or describe what isn't working]

RELEVANT FILES:
- modules/identifier.py
- modules/arctic_api.py
- config.py

WHAT CODEX BUILT:
Two public functions: identify_primary_control() (keyword + one-time poster filtering for r/studyAbroad) and identify_secondary_control() (random sampling for r/REU and r/college). Three private helpers for bot filtering, keyword matching, and deduplication.

CONSTRAINTS:
- Do not make direct HTTP calls in identifier.py — must use arctic_api functions
- All config values must come from config.py
- Do not add Streamlit imports
- Do not modify arctic_api.py or config.py unless the bug is provably caused by them
- User Record dict schema must stay exactly as specified

ACCEPTANCE CRITERIA:
1. identify_primary_control(target_n=10) returns non-empty list with correct schema
2. No duplicate usernames
3. Bot accounts excluded
4. Keyword matching is case-insensitive
5. identify_secondary_control returns random_sample users

DO NOT:
- Rewrite working functions
- Add CSV or UI logic
- Change the User Record schema

OUTPUT:
Fix the problem described above. Summarize what was changed, why, and list any follow-up issues for the next Claude Code session.
```
