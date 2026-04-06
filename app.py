"""Streamlit entry point for the Reddit Control Group Scraper."""

from pathlib import Path

import streamlit as st

from config import GROUPS


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
LOGS_DIR = PROJECT_ROOT / "logs"
PAGE_PATHS = {
    "primary_studyAbroad": "pages/01_primary_control.py",
    "secondary_REU": "pages/02_secondary_control_a.py",
    "secondary_college": "pages/03_secondary_control_b.py",
}


def ensure_runtime_directories() -> None:
    """Create local output directories required by the app."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)


def initialize_session_state() -> None:
    """Populate shared session state keys used across all workflow pages."""
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
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_group_card(group_key: str, group_config: dict[str, str]) -> None:
    """Render a single control-group card on the home screen."""
    with st.container(border=True):
        st.subheader(group_config["label"])
        st.caption(f"Target subreddit: r/{group_config['subreddit']}")
        st.write(group_config["description"])
        st.page_link(
            PAGE_PATHS[group_key],
            label="Configure & Run",
            icon=":material/arrow_forward:",
            use_container_width=True,
        )


def main() -> None:
    """Run the Streamlit home screen."""
    st.set_page_config(
        page_title="Reddit Control Group Scraper",
        page_icon="R",
        layout="wide",
    )
    ensure_runtime_directories()
    initialize_session_state()

    st.title("Reddit Control Group Scraper")
    st.write("Identify users, scrape full Reddit history, and export group CSVs.")

    if st.button("Run All Groups", type="primary", use_container_width=True):
        st.info("Run each control group from its workflow page so you can monitor progress clearly.")

    st.divider()

    for group_key, group_config in GROUPS.items():
        render_group_card(group_key, group_config)


if __name__ == "__main__":
    main()
