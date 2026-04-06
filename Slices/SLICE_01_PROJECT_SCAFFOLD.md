# SLICE_01_PROJECT_SCAFFOLD.md
# Reddit Control Group Scraper

## Goal
Create the complete project folder structure, configuration file, dependency list, and a functional Streamlit home screen with three group cards.

## Acceptance Criteria
1. Running `python3 -m streamlit run app.py` launches without errors
2. Home screen displays three cards: Primary Control (r/studyAbroad), Secondary Control A (r/REU), Secondary Control B (r/college)
3. Each card shows the group name, target subreddit, and a plain-English description of the sampling logic
4. Each card has a "Configure & Run" button (does not need to be functional yet — clicking it can show a placeholder message)
5. A "Run All Groups" button appears at the top of the home screen
6. `config.py` contains all hardcoded values: API base URL, subreddit names, default sample size, and full keyword list
7. All module files exist as empty stubs (importable but not yet implemented)
8. `requirements.txt` lists all dependencies with minimum version numbers
9. `/output` and `/logs` directories are created automatically if they don't exist when the app starts

## Files to Create
```
reddit_control_scraper/
├── app.py
├── requirements.txt
├── README.md
├── config.py
├── modules/
│   ├── __init__.py
│   ├── identifier.py
│   ├── scraper.py
│   ├── exporter.py
│   └── arctic_api.py
└── pages/
    ├── 01_primary_control.py
    ├── 02_secondary_control_a.py
    └── 03_secondary_control_b.py
```

## Component Contracts

### config.py
```python
ARCTIC_SHIFT_BASE_URL: str = "https://arctic-shift.photon-reddit.com"
DEFAULT_SAMPLE_SIZE: int = 500
REQUEST_DELAY_SECONDS: float = 1.0
MAX_RETRIES: int = 3

GROUPS: dict = {
    "primary_studyAbroad": {
        "label": "Primary External Control",
        "subreddit": "studyAbroad",
        "sampling": "keyword_and_one_time",
        "description": "r/studyAbroad users who posted only once or mentioned canceling their plans"
    },
    "secondary_REU": {
        "label": "Secondary External Control A",
        "subreddit": "REU",
        "sampling": "random",
        "description": "Random sample of r/REU users (students in research programs)"
    },
    "secondary_college": {
        "label": "Secondary External Control B",
        "subreddit": "college",
        "sampling": "random",
        "description": "Random sample of r/college users (general college student baseline)"
    }
}

CANCELLATION_KEYWORDS: list = [
    "cancel", "cancelled", "canceled",
    "withdrew", "withdraw",
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
    "deferred"
]
```

### app.py
- Renders page title and subtitle
- Creates `/output` and `/logs` directories if they don't exist
- Renders one `st.container()` card per group using data from `config.GROUPS`
- Each card shows: label, subreddit, description, and a "Configure & Run" button
- "Run All Groups" button at top (placeholder for now)

### Module stubs (identifier.py, scraper.py, exporter.py, arctic_api.py)
- Each file contains a module-level docstring describing its purpose
- Contains placeholder function signatures with `pass` as the body
- Must be importable without errors

## Edge Cases to Handle
- `/output` and `/logs` directories must be created silently on startup — no error if they already exist
- `config.py` must be importable from any module without circular imports

## Test Cases
1. Run `python3 -m streamlit run app.py` — browser opens, no errors in terminal
2. Home screen shows exactly three group cards with correct labels and subreddits
3. Run `python3 -c "import config; print(config.ARCTIC_SHIFT_BASE_URL)"` — prints the base URL
4. Run `python3 -c "from modules import identifier, scraper, exporter, arctic_api"` — no import errors

---

## Codex Generation Prompt

```
CONTEXT:
I am building a local Streamlit web app called "Reddit Control Group Scraper" for a psychology research lab. The app identifies Reddit users across three hardcoded control groups and scrapes their full post history via the ArcticShift public API (https://arctic-shift.photon-reddit.com). It is built in Python with Streamlit, httpx, and pandas.

TASK:
Create the complete project scaffold. This is Slice 1 of 6 — no scraping logic yet, just the folder structure, configuration, dependencies, and a working home screen.

FILES TO CREATE:
- app.py — Streamlit home screen with three group cards and a "Run All Groups" button
- config.py — all hardcoded config values (see CONSTRAINTS for exact content)
- requirements.txt — all dependencies with minimum version pins
- README.md — brief setup instructions (pip install, streamlit run)
- modules/__init__.py — empty
- modules/arctic_api.py — stub with docstring and empty function signatures
- modules/identifier.py — stub with docstring and empty function signatures
- modules/scraper.py — stub with docstring and empty function signatures
- modules/exporter.py — stub with docstring and empty function signatures
- pages/01_primary_control.py — stub Streamlit page, title only
- pages/02_secondary_control_a.py — stub Streamlit page, title only
- pages/03_secondary_control_b.py — stub Streamlit page, title only

CONSTRAINTS:
- Python 3.10+, Streamlit, httpx, pandas only
- config.py must contain exactly:
  - ARCTIC_SHIFT_BASE_URL = "https://arctic-shift.photon-reddit.com"
  - DEFAULT_SAMPLE_SIZE = 500
  - REQUEST_DELAY_SECONDS = 1.0
  - MAX_RETRIES = 3
  - GROUPS dict with keys: "primary_studyAbroad", "secondary_REU", "secondary_college"
  - Each group has: label, subreddit, sampling, description fields
  - CANCELLATION_KEYWORDS list with all 22 keywords listed below:
    cancel, cancelled, canceled, withdrew, withdraw, not going, didn't go,
    ended up not, never went, couldn't go, no longer going, not going anymore,
    won't be going, dropped out, pulled out, decided against, changed my mind,
    backing out, had to cancel, plans fell through, visa denied, couldn't afford, deferred
- app.py must create /output and /logs directories on startup if they don't exist
- Each module stub must be importable without errors
- Use st.container() for group cards on the home screen
- No database, no authentication, no external services beyond ArcticShift

ACCEPTANCE CRITERIA:
1. Running python3 -m streamlit run app.py launches without errors
2. Home screen shows three group cards with correct labels, subreddits, and descriptions
3. Each card has a "Configure & Run" button
4. A "Run All Groups" button appears at the top
5. python3 -c "from modules import identifier, scraper, exporter, arctic_api" runs without errors
6. /output and /logs directories are created automatically on startup

DO NOT:
- Implement any API calls, scraping logic, or data processing
- Add features outside this slice
- Leave broken imports or syntax errors
- Use placeholder comments like "TODO: implement this" — stubs should have docstrings instead

OUTPUT:
Write the complete implementation for all files listed above. After writing, list any assumptions you made.
```

---

## Claude Code Debugging Prompt

```
CONTEXT:
I am building a local Streamlit app called "Reddit Control Group Scraper." Slice 1 (project scaffold) was just generated by Codex. The app uses Python, Streamlit, httpx, and pandas. The entry point is app.py, launched with python3 -m streamlit run app.py.

CURRENT PROBLEM:
[Paste exact error message or describe what isn't working]

RELEVANT FILES:
- app.py
- config.py
- modules/__init__.py
- modules/arctic_api.py
- modules/identifier.py
- modules/scraper.py
- modules/exporter.py
- pages/01_primary_control.py
- pages/02_secondary_control_a.py
- pages/03_secondary_control_b.py

WHAT CODEX BUILT:
Slice 1 scaffold — folder structure, config.py with all hardcoded values, Streamlit home screen with three group cards, module stubs, page stubs, requirements.txt.

CONSTRAINTS:
- Do not add any scraping or API logic — that belongs in later slices
- Do not change the folder structure defined in ARCHITECTURE.md
- All config values must remain in config.py — do not hardcode them elsewhere
- Python 3.10+, Streamlit only for the UI layer

ACCEPTANCE CRITERIA:
1. Running python3 -m streamlit run app.py launches without errors
2. Home screen shows three group cards with correct labels and descriptions
3. All module files are importable without errors
4. /output and /logs directories are auto-created on startup

DO NOT:
- Rewrite files that are already working
- Add features beyond what Slice 1 specifies
- Change config values

OUTPUT:
Fix the problem described above. Summarize what was changed, why, and list any follow-up issues to address in the next Claude Code session.
```
