# SLICE_05_CSV_EXPORTER.md
# Reddit Control Group Scraper

## Goal
Build the `exporter.py` module, which takes a list of Post Record dicts, deduplicates them, splits them by control group, and writes three separate CSV files to the `/output` directory.

## Acceptance Criteria
1. `export_to_csv()` accepts a list of Post Record dicts and writes three CSV files — one per control group
2. Output files are named exactly: `primary_control_studyAbroad.csv`, `secondary_control_REU.csv`, `secondary_control_college.csv`
3. All files are written to the `/output` directory (created if it doesn't exist)
4. Posts are deduplicated by `post_id` before writing — no duplicate rows
5. Each CSV has exactly the columns defined in the Post Record schema (in the order specified below)
6. A summary dict is returned with row counts and file paths for each group
7. A run log entry is written to `/logs/run_YYYY-MM-DD_HH-MM.log` summarizing the export
8. Function is testable independently via plain Python script

## Files to Create or Modify
- `modules/exporter.py` — full implementation (replaces stub from Slice 1)

## Component Contracts

### Functions in `exporter.py`

```python
def export_to_csv(
    posts: list[dict],
    output_dir: str = "output"
) -> dict:
    """
    Deduplicates, splits by control group, and writes three CSV files.
    
    posts: flat list of Post Record dicts (output of scraper.py)
    output_dir: directory to write CSV files (default: "output")
    
    Returns a summary dict:
    {
        "primary_studyAbroad": {"rows": int, "filepath": str},
        "secondary_REU": {"rows": int, "filepath": str},
        "secondary_college": {"rows": int, "filepath": str},
        "total_rows": int,
        "duplicate_rows_removed": int
    }
    """

def write_run_log(
    summary: dict,
    log_dir: str = "logs"
) -> str:
    """
    Writes a plain-text run log summarizing the export.
    Log filename: run_YYYY-MM-DD_HH-MM.log
    Returns the filepath of the log file written.
    """
```

### CSV Column Order
Columns must appear in this exact order in every output file:
1. `username`
2. `control_group`
3. `source_subreddit`
4. `selection_reason`
5. `post_id`
6. `post_type`
7. `subreddit`
8. `title`
9. `body`
10. `score`
11. `created_utc`
12. `url`
13. `is_deleted`

### Run Log Format
```
Reddit Control Group Scraper — Export Log
Run timestamp: 2024-03-15 10:30:00 UTC
------------------------------------------
primary_studyAbroad:  1432 rows → output/primary_control_studyAbroad.csv
secondary_REU:         891 rows → output/secondary_control_REU.csv
secondary_college:    2103 rows → output/secondary_control_college.csv
------------------------------------------
Total rows exported:  4426
Duplicate rows removed: 12
```

## Edge Cases to Handle
- Empty group: if no posts exist for a control group, write an empty CSV with headers only — do not skip the file
- Missing keys in Post Record: fill with empty string in CSV — do not crash
- Output directory doesn't exist: create it before writing
- Logs directory doesn't exist: create it before writing
- Posts list is empty: write three empty CSVs with headers, return summary with all zeros

## Test Cases

```python
from modules.exporter import export_to_csv, write_run_log

# Test 1: Export real scraped data
# (assumes scraper.py from Slice 4 is working)
from modules.identifier import identify_secondary_control
from modules.scraper import scrape_users

users = identify_secondary_control("REU", "secondary_REU", target_n=3)
progress = {"completed": 0, "total": 3, "current_user": "", "status": "running", "failed_users": []}
posts = scrape_users(users, progress, [False])

summary = export_to_csv(posts)
assert "secondary_REU" in summary
assert summary["secondary_REU"]["rows"] > 0
assert summary["primary_studyAbroad"]["rows"] == 0   # no primary users in this test
print(f"✅ Test 1 passed — exported {summary['total_rows']} rows")

# Test 2: Deduplication works
import copy
doubled = posts + copy.deepcopy(posts)   # duplicate every post
summary2 = export_to_csv(doubled, output_dir="output/test")
assert summary2["duplicate_rows_removed"] == len(posts)
print(f"✅ Test 2 passed — {summary2['duplicate_rows_removed']} duplicates removed")

# Test 3: Empty input produces files with headers only
summary3 = export_to_csv([], output_dir="output/test_empty")
assert summary3["total_rows"] == 0
import os
assert os.path.exists("output/test_empty/primary_control_studyAbroad.csv")
print("✅ Test 3 passed — empty input creates header-only CSVs")

# Test 4: Run log is created
log_path = write_run_log(summary)
assert os.path.exists(log_path)
print(f"✅ Test 4 passed — log written to {log_path}")
```

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit app called "Reddit Control Group Scraper" for a psychology research lab. Slices 1-4 are complete: the scaffold, ArcticShift API wrapper, user identifier, and post history scraper are all working. The scraper produces a flat list of Post Record dicts. Now I need to write those records to CSV files.

TASK:
Implement modules/exporter.py — the module that deduplicates scraped post data, splits it by control group, and writes three CSV files plus a run log. This is Slice 5 of 6.

FILES TO CREATE:
- modules/exporter.py — full implementation (replaces stub from Slice 1)

CONSTRAINTS:
- Use pandas for deduplication and CSV writing
- Two public functions with exact signatures:
    export_to_csv(posts, output_dir) -> dict
    write_run_log(summary, log_dir) -> str
- Three output files named exactly:
    primary_control_studyAbroad.csv
    secondary_control_REU.csv
    secondary_control_college.csv
- CSV columns in this exact order:
    username, control_group, source_subreddit, selection_reason,
    post_id, post_type, subreddit, title, body, score, created_utc, url, is_deleted
- Deduplicate by post_id before writing
- If a control group has zero posts: write a CSV with headers only (do not skip the file)
- Missing Post Record keys: fill with empty string — do not crash
- Create output_dir and log_dir if they don't exist
- Log filename format: run_YYYY-MM-DD_HH-MM.log
- Return summary dict with: rows per group, filepath per group, total_rows, duplicate_rows_removed
- Do not import streamlit

ACCEPTANCE CRITERIA:
1. export_to_csv() writes exactly three CSV files to output_dir
2. Files have correct names and column order
3. Deduplication by post_id removes exact duplicate rows
4. Empty group produces a header-only CSV
5. write_run_log() creates a readable log file
6. Summary dict has correct row counts

DO NOT:
- Add Streamlit imports
- Modify any files outside modules/exporter.py
- Merge all groups into a single CSV — three separate files required
- Skip writing a file for empty groups

OUTPUT:
Write the complete implementation for modules/exporter.py. After writing, list any assumptions you made.
```

---

## Claude Code Debugging Prompt

```
CONTEXT:
I am building a local Streamlit app called "Reddit Control Group Scraper." Slice 5 (CSV exporter) was just generated by Codex. The module lives at modules/exporter.py and depends on pandas and Python's built-in os and datetime modules.

CURRENT PROBLEM:
[Paste exact error message or describe what isn't working]

RELEVANT FILES:
- modules/exporter.py
- config.py

WHAT CODEX BUILT:
export_to_csv() deduplicates Post Record dicts by post_id, splits by control_group, and writes three named CSV files to the output directory. write_run_log() writes a plain-text summary log.

CONSTRAINTS:
- Use pandas for all CSV operations
- Three separate output files — do not merge into one
- Column order must match spec exactly
- Empty groups must produce header-only files, not be skipped
- Do not add Streamlit imports
- Do not modify files outside exporter.py

ACCEPTANCE CRITERIA:
1. Three correctly named CSV files produced in output_dir
2. Correct column order
3. Deduplication works
4. Empty groups produce header-only files
5. Run log is created

DO NOT:
- Merge CSVs
- Skip empty groups
- Change column order

OUTPUT:
Fix the problem described above. Summarize what was changed, why, and list any follow-up issues for the next Claude Code session.
```
