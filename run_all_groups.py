"""Headless three-group rescrape driver (2026-06-24).

Orchestrates the EXISTING, tested pipeline modules — no reimplementation of
identification, scraping, API, or export logic. Runs all three control groups
end to end and writes the three per-group CSVs via the standard exporter.

Primary control uses the keyword_match bucket (DEC-R1, chosen 2026-06-23).
"""

import sys
import time
import threading

sys.path.insert(0, ".")

from config import DEFAULT_SAMPLE_SIZE
from modules.identifier import identify_keyword_matches, identify_secondary_control
from modules.scraper import start_scrape_thread
from modules.exporter import export_to_csv, write_run_log


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _identify_progress(label):
    state = {"last": 0}

    def cb(scanned, found):
        # throttle: print roughly every 5k scanned items
        if scanned - state["last"] >= 5000:
            state["last"] = scanned
            _log(f"  {label} identify: {scanned:,} scanned, {found} users found")

    return cb


def _scrape_group(label, users):
    """Scrape full histories for `users`, printing a heartbeat. Returns (records, failed)."""
    if not users:
        _log(f"  {label}: 0 users identified — skipping scrape")
        return [], []
    progress = {}
    cancel_flag = [False]
    _log(f"  {label}: scraping full history for {len(users)} users...")
    thread = start_scrape_thread(users, progress, cancel_flag)
    while thread.is_alive():
        time.sleep(20)
        done = progress.get("completed", 0)
        total = progress.get("total", len(users))
        cur = progress.get("current_user")
        _log(f"  {label}: {done}/{total} users scraped (current: {cur})")
    thread.join()
    records = progress.get("results", [])
    failed = progress.get("failed_users", [])
    _log(f"  {label}: DONE — {len(records):,} records, {len(failed)} failed users")
    return records, failed


def main():
    _log("=== Three-group rescrape START ===")
    n = DEFAULT_SAMPLE_SIZE
    all_records = []
    failed_by_group = {}

    # --- Primary: r/studyAbroad, keyword_match bucket ---
    _log(f"PRIMARY (r/studyAbroad, keyword_match, target_n={n}) — identifying...")
    primary_users, primary_cap = identify_keyword_matches(
        target_n=n, progress_callback=_identify_progress("primary")
    )
    _log(f"PRIMARY: {len(primary_users)} users identified (scan cap hit: {primary_cap})")
    rec, fail = _scrape_group("primary", primary_users)
    all_records.extend(rec)
    failed_by_group["primary_studyAbroad"] = fail

    # --- Secondary A: r/REU, random sample ---
    _log(f"SECONDARY A (r/REU, random, target_n={n}) — identifying...")
    reu_users, reu_cap = identify_secondary_control(
        "REU", "secondary_REU", target_n=n, progress_callback=_identify_progress("REU")
    )
    _log(f"REU: {len(reu_users)} users identified (scan cap hit: {reu_cap})")
    rec, fail = _scrape_group("REU", reu_users)
    all_records.extend(rec)
    failed_by_group["secondary_REU"] = fail

    # --- Secondary B: r/college, random sample ---
    _log(f"SECONDARY B (r/college, random, target_n={n}) — identifying...")
    college_users, college_cap = identify_secondary_control(
        "college", "secondary_college", target_n=n, progress_callback=_identify_progress("college")
    )
    _log(f"COLLEGE: {len(college_users)} users identified (scan cap hit: {college_cap})")
    rec, fail = _scrape_group("college", college_users)
    all_records.extend(rec)
    failed_by_group["secondary_college"] = fail

    # --- Export (splits by control_group into the three CSVs) ---
    _log(f"Exporting {len(all_records):,} total records...")
    summary = export_to_csv(all_records)
    log_path = write_run_log(summary)

    # --- Final report ---
    _log("=== FINAL SUMMARY ===")
    _log(f"Total rows written (deduped): {summary['total_rows']:,}")
    _log(f"Duplicate rows removed: {summary['duplicate_rows_removed']:,}")
    for gk in ("primary_studyAbroad", "secondary_REU", "secondary_college"):
        info = summary.get(gk, {})
        _log(f"  {gk}: {info.get('rows', 0):,} rows -> {info.get('filepath', '')}")
        if failed_by_group.get(gk):
            _log(f"    failed users ({len(failed_by_group[gk])}): {failed_by_group[gk][:20]}")
    _log(f"Run log: {log_path}")
    _log("=== Three-group rescrape COMPLETE ===")


if __name__ == "__main__":
    main()
