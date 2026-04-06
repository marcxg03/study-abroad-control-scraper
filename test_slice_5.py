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