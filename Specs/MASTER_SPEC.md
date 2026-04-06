# MASTER_SPEC.md
# Reddit Control Group Scraper
# Version 1.1 — Open Questions Resolved

## 1. Problem Statement
Psychological research on the effects of studying abroad requires control groups — Reddit users who are similar to study abroad participants but did not go. This tool automates the identification and data collection for three predefined control groups by scraping Reddit user histories via the ArcticShift API and exporting results as analysis-ready CSV files.

## 2. Target Users
Research lab members with basic technical literacy (comfortable running a terminal command to launch a local app). No coding knowledge required beyond initial setup.

## 3. User Stories
1. As a lab member, I want to identify r/studyAbroad users who canceled or only posted once, so that I can build my primary control group without manually reading thousands of posts.
2. As a lab member, I want to randomly sample users from r/REU and r/college, so that I can build my secondary control groups quickly.
3. As a lab member, I want to scrape the complete Reddit post history of every identified user, so that I have full behavioral data for analysis.
4. As a lab member, I want the scrape to run in the background, so that I can walk away and return when it's done.
5. As a lab member, I want results exported as separate CSV files per group, so that I can load each dataset directly into R or Python for analysis.

## 4. Feature List

### P0 — Must Have (Core MVP)
- **User Identification: Primary Control** — Query r/studyAbroad via ArcticShift, filter for one-time posters and cancellation-keyword matches, return a deduplicated list of usernames
- **User Identification: Secondary Controls** — Query r/REU and r/college via ArcticShift, return a random sample of usernames
- **Post History Scraper** — For any identified user list, fetch complete post and comment history across all subreddits via ArcticShift
- **Background Processing** — Scrape jobs run asynchronously so the UI stays responsive
- **CSV Export (per group)** — Output three separate CSV files, one per control group, named by group
- **Progress Indicator** — Show live progress during scraping (users completed / total)

### P1 — Important but Not Urgent
- **Sample Size Control** — Let the lab member set target N per group (default: 500)
- **Resume Interrupted Scrape** — If a scrape is interrupted, pick up where it left off rather than starting over
- **Deleted Post Flagging** — Include archived deleted/removed posts in output, marked with `is_deleted = True`

### P2 — Nice to Have
- **Duplicate Detection Across Groups** — Flag users who appear in more than one control group
- **Basic Run Log** — A plain text log file saved alongside the CSVs showing what was scraped and when

## 5. Screens and Flows

### Screen 1: Home / Group Selection
- Three cards, one per control group, each showing the group name, target subreddit, and sampling logic in plain English
- A "Configure & Run" button on each card
- A "Run All Groups" button at the top

### Screen 2: Group Configuration
- Sample size input (default 500)
- For Primary Control only: editable keyword list with defaults pre-filled
- "Start Identification" button

### Screen 3: Identification Results
- Table showing identified usernames, their subreddit of origin, and the reason they were selected (one-time poster / keyword match / random sample)
- Total count displayed prominently
- "Proceed to Scrape" button
- "Export User List" button (CSV of usernames only, before scraping)

### Screen 4: Scraping Progress
- Progress bar: X of N users scraped
- Estimated time remaining
- Live log of current activity (e.g., "Scraping u/username — 143 posts found")
- "Cancel" button

### Screen 5: Export
- Summary stats per group (total users, total posts, date range of data)
- "Download CSVs" button — downloads all three files
- Files saved locally to an /output folder in the project directory

### User Flow
Home → Configure Group → View Identified Users → Confirm → Scrape (background) → Export CSVs

## 6. Data Model

### User Record
- `username` — string — Reddit username
- `source_subreddit` — string — subreddit they were sampled from
- `control_group` — string — which of the three groups they belong to (values: "primary_studyAbroad", "secondary_REU", "secondary_college")
- `selection_reason` — string — "one_time_poster", "keyword_match", or "random_sample"
- `identified_at` — timestamp — when the user was identified

### Post Record
- `username` — string — Reddit username (links back to User Record)
- `post_id` — string — unique Reddit post or comment ID
- `subreddit` — string — subreddit where the post appeared
- `post_type` — string — "post" or "comment"
- `title` — string — post title (null for comments)
- `body` — string — post or comment text
- `score` — integer — upvotes minus downvotes
- `created_utc` — timestamp — when the post was made
- `url` — string — direct link to the post
- `is_deleted` — boolean — True if ArcticShift archived this post after it was deleted/removed on Reddit

### CSV Output Schema
One row per post. All fields from Post Record plus `control_group` and `source_subreddit` from User Record.

### Output File Naming Convention
- `primary_control_studyAbroad.csv`
- `secondary_control_REU.csv`
- `secondary_control_college.csv`

## 7. External Integrations

### ArcticShift API
- **Base URL**: `https://arctic-shift.photon-reddit.com`
- **Authentication**: None required — open public API
- **Rate limiting**: Monitor `X-RateLimit-Remaining` response header; default delay of 1 second between requests
- **Key endpoints used**:
  - `/api/posts/search` — search posts within a subreddit (for user identification)
  - `/api/comments/search` — search comments within a subreddit (for user identification)
  - `/api/posts/search?author={username}` — fetch all posts by a specific user
  - `/api/comments/search?author={username}` — fetch all comments by a specific user
- **No setup required** — lab members do not need an account or API key

## 8. Non-Functional Requirements
- **Performance**: Scraping rate-limited to respect ArcticShift limits — 1 second delay between requests by default
- **Reliability**: Failed requests retry up to 3 times before logging as failed and moving on
- **Transparency**: Every scrape session produces a run log alongside the CSVs
- **Portability**: App runs locally with a simple `pip install` + `streamlit run` — no cloud setup required
- **Data integrity**: Deduplicate posts by `post_id` before writing to CSV

## 9. Out of Scope
- Hosted or cloud-deployed version of the app
- Ability to add custom subreddits or groups beyond the three hardcoded ones
- Any analysis, visualization, or interpretation of the scraped data
- Authentication with Reddit's own API (we use ArcticShift exclusively)
- Scraping media attachments, images, or videos — text only

## 10. Open Questions — RESOLVED
1. ✅ **ArcticShift API access** — Free, public, no API key required. Rate limit applies for heavy usage; handled via built-in 1-second delay and `X-RateLimit-Remaining` header monitoring.
2. ✅ **ArcticShift coverage** — Assumed full coverage of r/REU and r/college. To be confirmed empirically during first test run.
3. ✅ **Deleted/removed posts** — Included in export, flagged with `is_deleted = True` column in CSV.
4. ✅ **CSV output structure** — Three separate CSV files, one per control group, named by group.

## 11. Cancellation Keywords (Primary Control Group)
The following keywords will be used to identify r/studyAbroad users who intended to study abroad but did not go. This list is editable in the UI.

**Confirmed keywords:**
- cancel, cancelled, canceled
- withdrew, withdraw
- not going
- didn't go
- ended up not
- never went
- couldn't go
- no longer going
- not going anymore
- won't be going
- dropped out
- pulled out
- decided against
- changed my mind
- backing out
- had to cancel
- plans fell through
- visa denied
- couldn't afford
- deferred
