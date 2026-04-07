"""Secondary Control A workflow page."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import streamlit as st

from config import DEFAULT_SAMPLE_SIZE, GROUPS, MAX_SUBREDDIT_SCAN_POSTS
from modules.exporter import export_to_csv
from modules.exporter import write_run_log
from modules.identifier import identify_secondary_control
from modules.scraper import start_scrape_thread


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGS_DIR = PROJECT_ROOT / "logs"
GROUP_KEY = "secondary_REU"
GROUP_CONFIG = GROUPS[GROUP_KEY]


def ensure_runtime_directories() -> None:
    """Create local output and log directories when the page loads directly."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)


def initialize_session_state() -> None:
    """Initialize shared state keys for the multipage workflow."""
    defaults = {
        "identified_users": [],
        "scraped_posts": [],
        "scrape_progress": {
            "status": "idle",
            "total": 0,
            "completed": 0,
            "current_user": None,
            "failed_users": [],
            "results": [],
        },
        "cancel_flag": [False],
        "scrape_thread": None,
        "export_summary": None,
        "cap_hit": False,
        "scan_summary": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "identification_progress" not in st.session_state:
        st.session_state["identification_progress"] = {"status": "idle"}


def reset_workflow_state() -> None:
    """Clear the current workflow state before starting a fresh run."""
    st.session_state.identified_users = []
    st.session_state.scraped_posts = []
    st.session_state.scrape_progress = {
        "status": "idle",
        "total": 0,
        "completed": 0,
        "current_user": None,
        "failed_users": [],
        "results": [],
    }
    st.session_state.cancel_flag = [False]
    st.session_state.scrape_thread = None
    st.session_state.export_summary = None
    st.session_state["cap_hit"] = False
    st.session_state["scan_summary"] = None
    st.session_state["identification_progress"] = {"status": "idle"}


def current_group_users() -> list[dict]:
    """Return identified users for the current control group."""
    return [
        user for user in st.session_state.identified_users
        if user.get("control_group") == GROUP_KEY
    ]


def current_group_posts() -> list[dict]:
    """Return scraped posts for the current control group."""
    return [
        post for post in st.session_state.scraped_posts
        if post.get("control_group") == GROUP_KEY
    ]


def sync_finished_scrape() -> None:
    """Capture thread output and build export files once scraping finishes."""
    thread = st.session_state.scrape_thread
    progress = st.session_state.scrape_progress

    if thread is not None and not thread.is_alive() and progress.get("status") in {"done", "cancelled"}:
        st.session_state.scraped_posts = progress.get("results", [])
        st.session_state.scrape_thread = None

        if st.session_state.export_summary is None:
            try:
                summary = export_to_csv(st.session_state.scraped_posts, OUTPUT_DIR)
                log_path = write_run_log(summary, LOGS_DIR)
                summary["run_log"] = log_path
                st.session_state.export_summary = summary
            except Exception:
                st.error("The scrape finished, but the export files could not be prepared.")


def render_results_table(users: list[dict]) -> None:
    """Show identified users in a compact table."""
    st.subheader("Results")
    with st.expander("ℹ️ What am I looking at?"):
        st.write(
            "This table shows the users identified for this control group. Each row "
            "is one user. 'selection_reason' tells you why they were included — "
            "either keyword_match, one_time_poster, or random_sample. Review the "
            "list before proceeding. When ready, click Start Scraping to collect "
            "their full Reddit post history."
        )
    if not users:
        st.info("No users identified yet. Run identification from the configuration section above.")
        return

    scan_summary = st.session_state.get("scan_summary")
    if scan_summary:
        st.caption(
            f"Scanned {scan_summary['posts_scanned']:,} posts from "
            f"r/{GROUP_CONFIG['subreddit']} · {scan_summary['users_found']} users matched criteria"
        )

    dataframe = pd.DataFrame(users)
    st.dataframe(dataframe, use_container_width=True, hide_index=True)

    if st.session_state.get("cap_hit", False):
        st.warning(
            "⚠️ The subreddit scan reached the 50,000 post safety ceiling "
            "before scanning the full subreddit. Identified users are drawn "
            "from the most recent 50,000 posts only. The full subreddit "
            "history was not searched."
        )


def render_progress_section(users: list[dict]) -> None:
    """Show scrape controls, live progress, and failed-user details."""
    progress = st.session_state.scrape_progress
    thread = st.session_state.scrape_thread

    st.subheader("Scrape Progress")
    with st.expander("ℹ️ What is happening now?"):
        st.write(
            "The tool is now fetching the complete Reddit post and comment history "
            "for each identified user across all subreddits — not just the one they "
            "were sampled from. This runs in the background and may take several "
            "minutes depending on the number of users. Do not close this tab. "
            "When complete, a download button will appear for this group's CSV file."
        )

    if users and progress.get("status") in {"idle", "done", "cancelled"} and thread is None:
        if st.button("Start Scraping", type="primary", use_container_width=True):
            try:
                st.session_state.cancel_flag = [False]
                st.session_state.scrape_progress = {
                    "status": "running",
                    "total": 0,
                    "completed": 0,
                    "current_user": None,
                    "failed_users": [],
                    "results": [],
                }
                st.session_state.scraped_posts = []
                st.session_state.export_summary = None
                st.session_state.scrape_thread = start_scrape_thread(
                    users,
                    st.session_state.scrape_progress,
                    st.session_state.cancel_flag,
                )
                st.rerun()
            except Exception:
                st.error("The background scrape could not be started. Please try again.")

    total = max(progress.get("total", 0), 1)
    completed = progress.get("completed", 0)
    st.progress(min(completed / total, 1.0))

    status = progress.get("status", "idle")
    if status == "running":
        st.write(f"Status: running. Completed {completed} of {progress.get('total', 0)} users.")
        st.caption("Scraping in progress — 5 users running concurrently...")
        if st.button("Cancel Scrape", use_container_width=True):
            st.session_state.cancel_flag[0] = True
            st.warning("Cancellation requested. The app will stop after the current user finishes.")
    elif status == "done":
        st.success(f"Scraping finished. Collected {len(current_group_posts())} posts and comments for this group.")
    elif status == "cancelled":
        st.warning(f"Scraping was cancelled after {completed} of {progress.get('total', 0)} users.")
    else:
        st.caption("Start scraping after you review the identified users.")

    failed_users = progress.get("failed_users", [])
    if failed_users:
        with st.expander("⚠️ Failed users"):
            st.write(failed_users)

    active_thread = st.session_state.scrape_thread
    if active_thread is not None and active_thread.is_alive():
        time.sleep(2)
        st.rerun()


def render_downloads() -> None:
    """Render download button for the secondary control A CSV once exports are available."""
    st.subheader("Downloads")
    summary = st.session_state.export_summary
    if not summary:
        st.info("CSV downloads will appear here after scraping finishes and exports are prepared.")
        return

    run_log = summary.get("run_log")
    if run_log:
        st.caption(f"Run log saved to: {run_log}")

    group_data = summary.get(GROUP_KEY, {})
    file_path = group_data.get("filepath")
    if not file_path:
        return

    path = Path(file_path)
    if not path.exists():
        return

    try:
        file_bytes = path.read_bytes()
    except OSError:
        st.error(f"The export file for {GROUPS[GROUP_KEY]['label']} could not be opened.")
        return

    st.download_button(
        label="⬇️ Download Secondary Control A CSV",
        data=file_bytes,
        file_name="secondary_control_REU.csv",
        mime="text/csv",
        use_container_width=True,
    )


def main() -> None:
    """Render the Secondary Control A workflow page."""
    st.set_page_config(page_title=GROUP_CONFIG["label"], page_icon="R", layout="wide")
    ensure_runtime_directories()
    initialize_session_state()
    sync_finished_scrape()

    st.title(GROUP_CONFIG["label"])
    st.caption(f"Target subreddit: r/{GROUP_CONFIG['subreddit']}")
    st.write(GROUP_CONFIG["description"])

    st.subheader("Configuration")
    with st.expander("ℹ️ What does this step do?"):
        st.write(
            "This step identifies Reddit users from the target subreddit who match "
            "the criteria for this control group. For the Primary Control group, "
            "we look for users who either posted only once or mentioned canceling "
            "their study abroad plans. For Secondary groups, we randomly sample "
            "active users. Adjust the sample size and keywords as needed, then "
            "click Identify Users to begin."
        )
    sample_size = st.number_input(
        "Target sample size",
        min_value=1,
        value=DEFAULT_SAMPLE_SIZE,
        step=1,
    )

    id_status = st.session_state.get("identification_progress", {}).get("status", "idle")

    if st.button("Identify Users", type="primary", use_container_width=True):
        reset_workflow_state()
        subreddit = GROUP_CONFIG["subreddit"]

        progress_bar = st.progress(0)
        status_text = st.empty()
        scan_stats = {"posts_scanned": 0, "users_found": 0}

        def update_progress(posts_scanned, users_found):
            scan_stats["posts_scanned"] = posts_scanned
            scan_stats["users_found"] = users_found
            progress_bar.progress(min(posts_scanned / MAX_SUBREDDIT_SCAN_POSTS, 1.0))
            status_text.caption(
                f"Scanning r/{subreddit} — {posts_scanned:,} posts scanned "
                f"· {users_found} users found so far"
            )

        with st.spinner("Identifying users..."):
            try:
                users, cap_hit = identify_secondary_control(
                    subreddit=subreddit,
                    group_key=GROUP_KEY,
                    target_n=int(sample_size),
                    progress_callback=update_progress,
                )
                st.session_state.identified_users = users
                st.session_state["cap_hit"] = cap_hit
                st.session_state["identification_progress"]["status"] = "done"
                st.session_state["scan_summary"] = {
                    "posts_scanned": scan_stats["posts_scanned"],
                    "users_found": scan_stats["users_found"],
                }
            except Exception as exc:
                st.error(f"Identification failed: {exc}")
                st.session_state["identification_progress"]["status"] = "error"

        st.rerun()

    if id_status != "idle":
        if st.button("Start Over", use_container_width=True):
            reset_workflow_state()
            st.rerun()

    users = current_group_users()
    render_results_table(users)
    render_progress_section(users)
    render_downloads()


if __name__ == "__main__":
    main()
