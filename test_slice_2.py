#Slice 2 Test
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