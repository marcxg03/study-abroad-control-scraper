"""User identification logic for the three hardcoded Reddit control groups."""

from __future__ import annotations

import random
from datetime import datetime, timezone

import config
from config import BOT_BLOCKLIST, CANCELLATION_KEYWORDS, DEFAULT_SAMPLE_SIZE, GROUPS
from modules import arctic_api


MAX_SUBREDDIT_SCAN_POSTS = getattr(config, "MAX_SUBREDDIT_SCAN_POSTS", 50000)
_PRIMARY_GROUP_KEY = "primary_studyAbroad"
_PRIMARY_SUBREDDIT = GROUPS[_PRIMARY_GROUP_KEY]["subreddit"]
_SELECTION_PRIORITY = {
    "random_sample": 0,
    "one_time_poster": 1,
    "keyword_match": 2,
}


def _is_bot(username) -> bool:
    """Return True when a username should be excluded from control-group sampling."""
    if not username:
        return True

    username_text = str(username)
    username_lower = username_text.lower()
    blocklist_lower = {bot_name.lower() for bot_name in BOT_BLOCKLIST}
    return (
        username_text == "[deleted]"
        or username_text == "AutoModerator"
        or username_lower == "automoderator"
        or username_lower in blocklist_lower
        or username_lower.endswith("_bot")
        or username_text.endswith("Bot")
    )


def _keyword_match(text, keywords) -> bool:
    """Return True when any keyword appears as a case-insensitive substring."""
    if not text:
        return False

    text_lower = str(text).lower()
    return any(str(keyword).lower() in text_lower for keyword in keywords if keyword)


def _deduplicate_users(users) -> list[dict]:
    """Return one user record per username, keeping the strongest selection reason."""
    deduplicated: dict[str, dict] = {}

    for user in users:
        username = user["username"]
        existing = deduplicated.get(username)
        if existing is None:
            deduplicated[username] = dict(user)
            continue

        existing_priority = _SELECTION_PRIORITY.get(existing["selection_reason"], -1)
        new_priority = _SELECTION_PRIORITY.get(user["selection_reason"], -1)
        if new_priority > existing_priority:
            deduplicated[username] = dict(user)

    return list(deduplicated.values())


def _utc_timestamp() -> str:
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _content_text(item: dict) -> str:
    """Combine known text-bearing fields into one searchable string."""
    parts = [
        item.get("title"),
        item.get("selftext"),
        item.get("body"),
        item.get("text"),
    ]
    return " ".join(str(part) for part in parts if part)


def identify_primary_control(keywords=None, target_n=None, progress_callback=None) -> tuple[list[dict], bool]:
    """Identify the primary study abroad control users from posts and comments."""
    keyword_list = keywords or CANCELLATION_KEYWORDS
    requested_n = target_n or DEFAULT_SAMPLE_SIZE
    identified_at = _utc_timestamp()

    post_fields = ["id", "author", "title", "selftext", "created_utc"]
    comment_fields = ["id", "author", "body", "created_utc"]

    user_activity_counts: dict[str, int] = {}
    keyword_matched_users: set[str] = set()
    scanned_posts = 0
    scanned_comments = 0

    def _count_qualifying() -> int:
        return sum(
            1 for u, c in user_activity_counts.items()
            if u in keyword_matched_users or c == 1
        )

    for page in arctic_api.get_subreddit_posts_stream(
        _PRIMARY_SUBREDDIT,
        fields=post_fields,
        limit_per_request=100,
        max_results=MAX_SUBREDDIT_SCAN_POSTS,
    ):
        scanned_posts += len(page)
        for item in page:
            username = item.get("author")
            if _is_bot(username):
                continue
            user_activity_counts[username] = user_activity_counts.get(username, 0) + 1
            if _keyword_match(_content_text(item), keyword_list):
                keyword_matched_users.add(username)

        currently_found = _count_qualifying()
        if progress_callback is not None:
            progress_callback(scanned_posts, currently_found)
        if currently_found >= requested_n:
            break

    if _count_qualifying() < requested_n:
        for page in arctic_api.get_subreddit_comments_stream(
            _PRIMARY_SUBREDDIT,
            fields=comment_fields,
            limit_per_request=100,
            max_results=MAX_SUBREDDIT_SCAN_POSTS,
        ):
            scanned_comments += len(page)
            for item in page:
                username = item.get("author")
                if _is_bot(username):
                    continue
                user_activity_counts[username] = user_activity_counts.get(username, 0) + 1
                if _keyword_match(_content_text(item), keyword_list):
                    keyword_matched_users.add(username)

            currently_found = _count_qualifying()
            if progress_callback is not None:
                progress_callback(scanned_posts + scanned_comments, currently_found)
            if currently_found >= requested_n:
                break

    cap_hit = scanned_posts >= MAX_SUBREDDIT_SCAN_POSTS or scanned_comments >= MAX_SUBREDDIT_SCAN_POSTS

    users: list[dict] = []
    for username, activity_count in user_activity_counts.items():
        if username in keyword_matched_users:
            selection_reason = "keyword_match"
        elif activity_count == 1:
            selection_reason = "one_time_poster"
        else:
            continue

        users.append(
            {
                "username": username,
                "source_subreddit": _PRIMARY_SUBREDDIT,
                "control_group": _PRIMARY_GROUP_KEY,
                "selection_reason": selection_reason,
                "identified_at": identified_at,
            }
        )

    deduplicated_users = _deduplicate_users(users)
    deduplicated_users.sort(
        key=lambda user: (
            -_SELECTION_PRIORITY.get(user["selection_reason"], -1),
            user["username"].lower(),
        )
    )
    return deduplicated_users[:requested_n], cap_hit


def identify_secondary_control(subreddit, group_key, target_n=None, progress_callback=None) -> tuple[list[dict], bool]:
    """Identify a random sample of non-bot users from a secondary control subreddit."""
    requested_n = target_n or DEFAULT_SAMPLE_SIZE
    identified_at = _utc_timestamp()

    fields = ["id", "author", "created_utc"]
    candidate_usernames: set[str] = set()
    scanned_posts = 0
    scanned_comments = 0

    for page in arctic_api.get_subreddit_posts_stream(
        subreddit,
        fields=fields,
        limit_per_request=100,
        max_results=MAX_SUBREDDIT_SCAN_POSTS,
    ):
        scanned_posts += len(page)
        for item in page:
            username = item.get("author")
            if _is_bot(username):
                continue
            candidate_usernames.add(username)

        if progress_callback is not None:
            progress_callback(scanned_posts, len(candidate_usernames))
        if len(candidate_usernames) >= requested_n:
            break

    if len(candidate_usernames) < requested_n:
        for page in arctic_api.get_subreddit_comments_stream(
            subreddit,
            fields=fields,
            limit_per_request=100,
            max_results=MAX_SUBREDDIT_SCAN_POSTS,
        ):
            scanned_comments += len(page)
            for item in page:
                username = item.get("author")
                if _is_bot(username):
                    continue
                candidate_usernames.add(username)

            if progress_callback is not None:
                progress_callback(scanned_posts + scanned_comments, len(candidate_usernames))
            if len(candidate_usernames) >= requested_n:
                break

    cap_hit = scanned_posts >= MAX_SUBREDDIT_SCAN_POSTS or scanned_comments >= MAX_SUBREDDIT_SCAN_POSTS

    deduplicated_usernames = sorted(candidate_usernames, key=str.lower)
    sample_size = min(requested_n, len(deduplicated_usernames))
    sampled_usernames = random.sample(deduplicated_usernames, sample_size) if sample_size else []

    users = [
        {
            "username": username,
            "source_subreddit": subreddit,
            "control_group": group_key,
            "selection_reason": "random_sample",
            "identified_at": identified_at,
        }
        for username in sampled_usernames
    ]

    return _deduplicate_users(users), cap_hit
