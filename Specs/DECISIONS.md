# DECISIONS.md
# Reddit Control Group Scraper

## How to use this file
Any time a significant architectural or design decision is made during implementation — especially if it deviates from the spec — record it here with the reasoning. This protects you when you come back to this project months later wondering "why did we do it this way?"

---

## Pre-build Decisions (locked before coding began)

### DEC-001: Use Streamlit instead of Next.js
**Decision**: Build as a local Streamlit app
**Reason**: Lab members are comfortable with terminal but don't need a polished consumer product. Streamlit runs locally with minimal setup and the team has prior experience with it.
**Tradeoff**: Less visual polish, limited concurrency — acceptable for an internal research tool.

### DEC-002: ArcticShift as sole data source
**Decision**: Use ArcticShift public API exclusively — no Reddit API credentials required
**Reason**: ArcticShift is free, requires no authentication, and archives deleted posts which are valuable for research completeness.
**Tradeoff**: ArcticShift has no uptime guarantees and may have occasional data gaps.

### DEC-003: Three separate CSV output files
**Decision**: One CSV per control group, not a single merged file
**Reason**: Researchers will typically analyze each group separately in R or Python. Separate files reduce the need for downstream filtering steps.
**Tradeoff**: Users who want a merged dataset must join files themselves.

### DEC-004: Hardcoded groups, not configurable
**Decision**: Three control groups are hardcoded in config.py — not user-configurable in the UI
**Reason**: This is a long-term single-project tool. Flexibility adds complexity without payoff for this team.
**Tradeoff**: Adding a new group requires a code change rather than a UI click.

### DEC-005: Synchronous httpx in a background thread
**Decision**: Use synchronous httpx inside a threading.Thread rather than async/await
**Reason**: Streamlit's session state interacts more predictably with threads than with asyncio event loops.
**Tradeoff**: Slightly less efficient than pure async, but more debuggable and stable for this use case.

### DEC-006: Include deleted/removed posts
**Decision**: Include posts archived by ArcticShift even if deleted on Reddit; flag with is_deleted = True
**Reason**: Deleted posts represent real behavior and may be analytically important. Researchers can filter them out if needed.
**Tradeoff**: CSV files will contain [removed] and [deleted] body text — researchers must account for this.

---

## Implementation Decisions
*Add entries here as they arise during each slice build.*
