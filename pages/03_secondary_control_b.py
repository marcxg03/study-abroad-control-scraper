"""Secondary Control B workflow page."""

from __future__ import annotations

import threading
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
GROUP_KEY = "secondary_college"
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
        "identification_progress": {
            "posts_scanned": 0,
            "users_found": 0,
            "status": "idle",
            "result": None,
            "error": None,
        },
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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
    st.session_state["identification_progress"] = {
        "posts_scanned": 0,
        "users_found": 0,
        "status": "idle",
        "result": None,
        "error": None,
    }


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
    """Render download button for the secondary control B CSV once exports are available."""
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
        label="⬇️ Download Secondary Control B CSV",
        data=file_bytes,
        file_name="secondary_control_college.csv",
        mime="text/csv",
        use_container_width=True,
    )


def main() -> None:
    """Render the Secondary Control B workflow page."""
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

    id_progress = st.session_state.get("identification_progress", {})
    id_status = id_progress.get("status", "idle")

    if id_status == "done" and id_progress.get("result") is not None:
        users_result, cap_hit = id_progress["result"]
        st.session_state.identified_users = users_result
        st.session_state["cap_hit"] = cap_hit
        id_progress["result"] = None

    if id_status in ("idle", "done", "error"):
        if id_status == "error":
            st.error(id_progress.get("error") or "The app could not identify Secondary Control B users right now. Please try again.")
        if st.button("Identify Users", type="primary", use_container_width=True):
            reset_workflow_state()
            id_prog = {
                "posts_scanned": 0,
                "users_found": 0,
                "status": "running",
                "result": None,
                "error": None,
            }
            st.session_state["identification_progress"] = id_prog

            def _run_identification(prog=id_prog, n=int(sample_size)):
                def callback(posts_scanned, users_found):
                    prog["posts_scanned"] = posts_scanned
                    prog["users_found"] = users_found
                try:
                    result = identify_secondary_control(
                        subreddit=GROUP_CONFIG["subreddit"],
                        group_key=GROUP_KEY,
                        target_n=n,
                        progress_callback=callback,
                    )
                    prog["result"] = result
                    prog["status"] = "done"
                except Exception as exc:
                    prog["status"] = "error"
                    prog["error"] = str(exc)

            threading.Thread(target=_run_identification, daemon=True).start()
            st.rerun()

    elif id_status == "running":
        posts_scanned = id_progress.get("posts_scanned", 0)
        users_found = id_progress.get("users_found", 0)
        st.progress(min(posts_scanned / MAX_SUBREDDIT_SCAN_POSTS, 1.0))
        st.caption(
            f"Scanning r/{GROUP_CONFIG['subreddit']} — "
            f"{posts_scanned:,} posts scanned · {users_found} users found so far"
        )
        time.sleep(1)
        st.rerun()

    users = current_group_users()
    render_results_table(users)
    render_progress_section(users)
    render_downloads()


if __name__ == "__main__":
    main()
