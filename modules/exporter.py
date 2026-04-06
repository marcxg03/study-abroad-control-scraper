"""CSV export helpers for scraped Reddit control-group data."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


CSV_COLUMNS = [
    "username",
    "control_group",
    "source_subreddit",
    "selection_reason",
    "post_id",
    "post_type",
    "subreddit",
    "title",
    "body",
    "score",
    "created_utc",
    "url",
    "is_deleted",
]

GROUP_FILE_NAMES = {
    "primary_studyAbroad": "primary_control_studyAbroad.csv",
    "secondary_REU": "secondary_control_REU.csv",
    "secondary_college": "secondary_control_college.csv",
}


def _normalize_posts(posts) -> pd.DataFrame:
    """Return a DataFrame with all expected export columns present."""
    normalized_rows = []
    for post in posts:
        row = {}
        for column in CSV_COLUMNS:
            value = post.get(column, "") if isinstance(post, dict) else ""
            row[column] = "" if value is None else value
        normalized_rows.append(row)

    if not normalized_rows:
        return pd.DataFrame(columns=CSV_COLUMNS)

    return pd.DataFrame(normalized_rows, columns=CSV_COLUMNS)


def export_to_csv(posts, output_dir="output") -> dict:
    """Deduplicate scraped posts and write one CSV per control group."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    dataframe = _normalize_posts(posts)
    original_row_count = len(dataframe)
    deduplicated = dataframe.drop_duplicates(subset=["post_id"], keep="first")
    duplicate_rows_removed = original_row_count - len(deduplicated)

    summary = {
        "total_rows": int(len(deduplicated)),
        "duplicate_rows_removed": int(duplicate_rows_removed),
    }

    for group_key, file_name in GROUP_FILE_NAMES.items():
        group_frame = deduplicated[deduplicated["control_group"] == group_key]
        destination = output_path / file_name
        group_frame.to_csv(destination, index=False, columns=CSV_COLUMNS)

        summary[group_key] = {
            "rows": int(len(group_frame)),
            "filepath": str(destination),
        }

    return summary


def write_run_log(summary, log_dir="logs") -> str:
    """Write a readable plain-text run log from an export summary."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    destination = log_path / f"run_{timestamp}.log"

    lines = [
        "Reddit Control Group Scraper Run Log",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Total rows written: {summary.get('total_rows', 0)}",
        f"Duplicate rows removed: {summary.get('duplicate_rows_removed', 0)}",
        "",
        "Per-group output:",
    ]

    for group_key in GROUP_FILE_NAMES:
        group_data = summary.get(group_key, {})
        lines.append(f"- {group_key}: {group_data.get('rows', 0)} rows")
        lines.append(f"  File: {group_data.get('filepath', '')}")

    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(destination)
