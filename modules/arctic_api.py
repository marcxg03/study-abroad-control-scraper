"""HTTP client helpers for interacting with the ArcticShift public API."""

from __future__ import annotations

import time

import httpx

from config import ARCTIC_SHIFT_BASE_URL, MAX_RESULTS_PER_CALL, MAX_RETRIES, REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS


def _make_request(endpoint, params) -> dict:
    """Send one HTTP request to ArcticShift with retries and rate-limit handling."""
    url = f"{ARCTIC_SHIFT_BASE_URL}{endpoint}"
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(REQUEST_DELAY_SECONDS)

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = client.get(url, params=params)
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            continue

        remaining_header = response.headers.get("X-RateLimit-Remaining")
        if remaining_header is not None:
            try:
                if float(remaining_header) < 5:
                    time.sleep(5)
            except ValueError:
                pass

        if response.status_code == 429:
            last_error = httpx.HTTPStatusError(
                "ArcticShift rate limit reached.",
                request=response.request,
                response=response,
            )
            if attempt == MAX_RETRIES:
                break
            time.sleep(30)
            continue

        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            continue

        if isinstance(payload, dict):
            return payload

        last_error = TypeError("ArcticShift response payload was not a JSON object.")
        if attempt == MAX_RETRIES:
            break

    raise RuntimeError(f"Request to ArcticShift failed for endpoint {endpoint}.") from last_error


def _normalize_fields(item: dict, fields: list[str] | None) -> dict:
    """Ensure requested fields exist in each returned record."""
    normalized_item = dict(item)
    if not fields:
        return normalized_item

    for field_name in fields:
        normalized_item.setdefault(field_name, None)

    return normalized_item


def _paginate(endpoint: str, params: dict, fields: list[str] | None, max_results: int = MAX_RESULTS_PER_CALL) -> list[dict]:
    """Fetch pages for a search endpoint, stopping at max_results or when data runs out."""
    results: list[dict] = []
    request_params = dict(params)
    seen_cursors: set[str] = set()

    while True:
        payload = _make_request(endpoint, request_params)
        batch = payload.get("data", [])

        if not isinstance(batch, list) or not batch:
            break

        results.extend(_normalize_fields(item, fields) for item in batch if isinstance(item, dict))

        if max_results is not None and len(results) >= max_results:
            break

        last_item = next((item for item in reversed(batch) if isinstance(item, dict)), None)
        if last_item is None:
            break

        cursor = last_item.get("created_utc")
        if not cursor or cursor in seen_cursors:
            break

        seen_cursors.add(cursor)
        request_params["after"] = cursor

    return results[:max_results] if max_results is not None else results


def _prepare_fields(fields) -> list[str] | None:
    """Convert supported field input into a normalized list of field names."""
    if fields is None:
        return None

    if isinstance(fields, str):
        field_names = [field.strip() for field in fields.split(",") if field.strip()]
        return field_names or None

    field_names = [str(field).strip() for field in fields if str(field).strip()]
    return field_names or None


def _build_params(key: str, value: str, fields, limit_per_request: int) -> tuple[dict, list[str] | None]:
    """Build common ArcticShift search parameters for paginated list endpoints."""
    normalized_fields = _prepare_fields(fields)
    params = {
        key: value,
        "limit": limit_per_request,
        "sort": "asc",
    }

    if normalized_fields:
        params["fields"] = ",".join(normalized_fields)

    return params, normalized_fields


def get_subreddit_posts(subreddit, fields=None, limit_per_request=100, max_results=MAX_RESULTS_PER_CALL) -> list[dict]:
    """Return paginated posts for a subreddit, up to max_results items."""
    params, normalized_fields = _build_params("subreddit", subreddit, fields, limit_per_request)
    return _paginate("/api/posts/search", params, normalized_fields, max_results)


def get_subreddit_comments(subreddit, fields=None, limit_per_request=100, max_results=MAX_RESULTS_PER_CALL) -> list[dict]:
    """Return paginated comments for a subreddit, up to max_results items."""
    params, normalized_fields = _build_params("subreddit", subreddit, fields, limit_per_request)
    return _paginate("/api/comments/search", params, normalized_fields, max_results)


def get_user_posts(username, fields=None, limit_per_request=100, max_results=MAX_RESULTS_PER_CALL) -> list[dict]:
    """Return paginated posts for a user, up to max_results items."""
    params, normalized_fields = _build_params("author", username, fields, limit_per_request)
    return _paginate("/api/posts/search", params, normalized_fields, max_results)


def get_user_comments(username, fields=None, limit_per_request=100, max_results=MAX_RESULTS_PER_CALL) -> list[dict]:
    """Return paginated comments for a user, up to max_results items."""
    params, normalized_fields = _build_params("author", username, fields, limit_per_request)
    return _paginate("/api/comments/search", params, normalized_fields, max_results)
