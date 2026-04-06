#Slice 3 Test
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