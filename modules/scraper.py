"""Scraping helpers for collecting full Reddit histories for identified users."""

from __future__ import annotations

import concurrent.futures
import threading
from datetime import datetime, timezone

import config
from modules import arctic_api

MAX_CONCURRENT_USERS = getattr(config, "MAX_CONCURRENT_USERS", 5)


def _to_iso_utc(created_utc) -> str | None:
    """Convert a Unix timestamp into an ISO 8601 UTC string."""
    if created_utc is None:
        return None

    try:
        timestamp = int(created_utc)
    except (TypeError, ValueError):
        return None

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _is_deleted_record(author, body) -> bool:
    """Return True when the content appears deleted or removed."""
    author_text = str(author).strip().lower() if author is not None else ""
    body_text = str(body).strip().lower() if body is not None else ""
    return author_text == "[deleted]" or body_text in {"[removed]", "[deleted]"}


def _comment_url(permalink) -> str | None:
    """Build an absolute Reddit URL for a comment when a permalink is available."""
    if not permalink:
        return None

    return f"https://reddit.com{permalink}"


def _build_post_record(user: dict, item: dict, post_type: str) -> dict:
    """Normalize a raw ArcticShift item into the app's Post Record schema."""
    if post_type == "post":
        body = item.get("selftext")
        url = item.get("url") or _comment_url(item.get("permalink"))
        title = item.get("title")
    else:
        body = item.get("body")
        url = _comment_url(item.get("permalink"))
        title = None

    return {
        "username": user.get("username"),
        "control_group": user.get("control_group"),
        "source_subreddit": user.get("source_subreddit"),
        "selection_reason": user.get("selection_reason"),
        "post_id": item.get("id"),
        "post_type": post_type,
        "subreddit": item.get("subreddit"),
        "title": title,
        "body": body,
        "score": item.get("score"),
        "created_utc": _to_iso_utc(item.get("created_utc")),
        "url": url,
        "is_deleted": _is_deleted_record(item.get("author"), body),
    }


def _scrape_single_user(user: dict) -> list[dict]:
    """Fetch and normalize all posts and comments for one identified user."""
    username = user.get("username")

    # fields=None fetches all available fields, including 'permalink' which the
    # ArcticShift API returns in the response body but rejects as a fields filter param.
    posts = arctic_api.get_user_posts(
        username,
        fields=None,
        limit_per_request=100,
        max_results=None,
    )
    comments = arctic_api.get_user_comments(
        username,
        fields=None,
        limit_per_request=100,
        max_results=None,
    )

    records = [_build_post_record(user, item, "post") for item in posts if isinstance(item, dict)]
    records.extend(_build_post_record(user, item, "comment") for item in comments if isinstance(item, dict))
    return records


def scrape_users(users, progress, cancel_flag) -> list[dict]:
    """Scrape full Reddit histories for a list of identified users, up to MAX_CONCURRENT_USERS at a time."""
    progress["total"] = len(users)
    progress["completed"] = progress.get("completed", 0)
    progress["failed_users"] = progress.get("failed_users", [])
    progress["status"] = "running"
    progress["results"] = progress.get("results", [])
    progress["current_user"] = None

    scraped_records: list[dict] = []
    lock = threading.Lock()

    def _scrape_and_track(user: dict) -> list[dict]:
        username = user.get("username")
        with lock:
            progress["current_user"] = username
        try:
            return _scrape_single_user(user)
        except Exception:
            with lock:
                progress["failed_users"].append(username)
            return []

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_USERS)
    try:
        futures: dict[concurrent.futures.Future, dict] = {}
        for user in users:
            if cancel_flag[0]:
                break
            futures[executor.submit(_scrape_and_track, user)] = user

        for future in concurrent.futures.as_completed(futures):
            records = future.result()
            with lock:
                scraped_records.extend(records)
                progress["completed"] += 1
                progress["results"] = list(scraped_records)

            if cancel_flag[0]:
                progress["status"] = "cancelled"
                return scraped_records
    finally:
        executor.shutdown(wait=False)

    if cancel_flag[0]:
        progress["status"] = "cancelled"
        return scraped_records

    progress["status"] = "done"
    return scraped_records


def start_scrape_thread(users, progress, cancel_flag) -> threading.Thread:
    """Launch scrape_users in a daemon thread and store its result on progress."""

    def _run() -> None:
        progress["results"] = scrape_users(users, progress, cancel_flag)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread
