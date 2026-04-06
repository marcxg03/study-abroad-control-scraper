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