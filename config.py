"""Hardcoded configuration values for the Reddit Control Group Scraper."""

ARCTIC_SHIFT_BASE_URL = "https://arctic-shift.photon-reddit.com"
DEFAULT_SAMPLE_SIZE = 500
REQUEST_DELAY_SECONDS = 0.1
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 3
MAX_RESULTS_PER_CALL = 500
MAX_SUBREDDIT_SCAN_POSTS = 50000
MAX_CONCURRENT_USERS = 5
BOT_BLOCKLIST = [
    "AutoModerator",
    "RemindMeBot",
    "WikiTextBot",
    "RepostSleuthBot",
]

GROUPS = {
    "primary_studyAbroad": {
        "label": "Primary External Control",
        "subreddit": "studyAbroad",
        "sampling": "keyword_and_one_time",
        "description": "r/studyAbroad users who posted only once or mentioned canceling their plans",
    },
    "secondary_REU": {
        "label": "Secondary External Control A",
        "subreddit": "REU",
        "sampling": "random",
        "description": "Random sample of r/REU users (students in research programs)",
    },
    "secondary_college": {
        "label": "Secondary External Control B",
        "subreddit": "college",
        "sampling": "random",
        "description": "Random sample of r/college users (general college student baseline)",
    },
}

CANCELLATION_KEYWORDS = [
    "cancel",
    "cancelled",
    "canceled",
    "withdrew",
    "withdraw",
    "not going",
    "didn't go",
    "ended up not",
    "never went",
    "couldn't go",
    "no longer going",
    "not going anymore",
    "won't be going",
    "dropped out",
    "pulled out",
    "decided against",
    "changed my mind",
    "backing out",
    "had to cancel",
    "plans fell through",
    "visa denied",
    "couldn't afford",
    "deferred",
]
