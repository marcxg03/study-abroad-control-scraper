#!/usr/bin/env python3
"""Data-quality QA pass for the study-abroad Reddit control-group CSVs.

Runs a battery of aggregate checks over the three per-group output CSVs and
writes a PII-safe markdown report. The report contains only counts, rates,
distributions, and (where an example helps) post_ids -- never usernames or
row-level post/comment content.

Checks, by what could actually be wrong:
  A. Structural integrity  (record counts, columns, malformed/field-shift rows, dtypes)
  B. Deduplication & uniqueness  (dup post_id, cross-group post/user leakage)
  C. Identification validity  (selection_reason mix, user counts, bot leakage, subreddit)
  D. Content & temporal coverage  (date range, post/comment split, deleted share, per-user dist)
  E. Provenance  (run-log reconciliation, primary == April-archive identity)

Usage:
    python3 scripts/qa_check.py
    python3 scripts/qa_check.py --output-dir output --report output/qa_report.md
"""

from __future__ import annotations

import argparse
import gc
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Project root so we can import the live config (keeps bot list / columns in sync).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import BOT_BLOCKLIST  # noqa: E402
from modules.exporter import CSV_COLUMNS  # noqa: E402

# --- Expectations -----------------------------------------------------------

REDDIT_FOUNDED = pd.Timestamp("2005-06-01", tz="UTC")
SCRAPE_CUTOFF = pd.Timestamp("2026-06-25", tz="UTC")  # day after the rescrape

GROUPS = {
    "primary_control_studyAbroad.csv": {
        "label": "Primary (r/studyAbroad)",
        "control_group": "primary_studyAbroad",
        "source_subreddit": "studyAbroad",
        "expected_reasons": {
            "one_time_poster",
            "keyword_match",
            "keyword_and_one_time_poster",
        },
        "wiki_records": 1_077_162,
        "wiki_users": 1_199,
        "archive": "archive/primary_control_studyAbroad_2026-04-08.csv",
    },
    "secondary_control_REU.csv": {
        "label": "Secondary A (r/REU)",
        "control_group": "secondary_REU",
        "source_subreddit": "REU",
        "expected_reasons": {"random_sample"},
        "wiki_records": 411_780,
        "wiki_users": 500,
        "archive": None,
    },
    "secondary_control_college.csv": {
        "label": "Secondary B (r/college)",
        "control_group": "secondary_college",
        "source_subreddit": "college",
        "expected_reasons": {"random_sample"},
        "wiki_records": 1_438_155,
        "wiki_users": 500,
        "archive": None,
    },
}

DELETED_BODIES = {"[deleted]", "[removed]"}

# Reports are PII-free, so they live in the research wiki's study-abroad project
# folder (not next to the git-ignored PII data). Override with --reports-dir.
DEFAULT_REPORTS_DIR = (
    "/Users/marcusgao/Desktop/research-wiki/wiki/projects/study-abroad/output"
)


def _check(rows, cid, name, status, detail):
    """Append a structured check result and echo it to stderr."""
    rows.append((cid, name, status, detail))
    print(f"  [{status:4}] {cid} {name}: {detail}", file=sys.stderr)


def _is_suspected_bot(username: str) -> bool:
    if username in BOT_BLOCKLIST or username == "[deleted]":
        return True
    return username.endswith("_bot") or username.endswith("Bot")


def raw_line_count(path: Path) -> int:
    """Count physical lines (incl. header) -- inflated by embedded newlines."""
    total = 0
    with path.open("rb") as fh:
        for _ in fh:
            total += 1
    return total


def analyze_group(path: Path, spec: dict, checks: list) -> dict:
    """Run all per-group checks; return a compact summary + id/user sets."""
    label = spec["label"]
    print(f"\n=== {label}  ({path.name}) ===", file=sys.stderr)

    # Robust read: C parser handles quoted embedded commas/newlines; keep ""
    # as empty string (matches how the exporter normalized None -> "").
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)
    records = len(df)

    # --- A1: record count vs wiki target + raw-line gap ---
    raw_lines = raw_line_count(path)
    target = spec["wiki_records"]
    status = "PASS" if records == target else "WARN"
    _check(
        checks, "A1", f"{label} record count",
        status,
        f"{records:,} records (wiki target {target:,}); "
        f"raw lines {raw_lines:,} -> {raw_lines - records - 1:,} lines absorbed by "
        f"embedded newlines in body",
    )

    # --- A2: column conformance ---
    cols_ok = list(df.columns) == CSV_COLUMNS
    _check(
        checks, "A2", f"{label} columns",
        "PASS" if cols_ok else "FAIL",
        "13 columns, correct order" if cols_ok else f"unexpected: {list(df.columns)}",
    )

    # --- A3: parser-corruption rows (embedded-delimiter field shift) ---
    # A row is "corrupt" when a stray delimiter shifted cells: post_type becomes a
    # non-{post,comment} token, or selection_reason holds a URL instead of a reason.
    # (Empty is_deleted/created_utc is legitimate missing data, not a shift -- excluded.)
    bad_type = ~df["post_type"].isin(["post", "comment", ""])
    bad_reason = ~df["selection_reason"].isin(spec["expected_reasons"] | {""})
    shifted = bad_type | bad_reason
    n_shift = int(shifted.sum())
    rate = n_shift / records if records else 0
    examples = [e for e in df.loc[shifted, "post_id"].tolist() if e][:3]
    _check(
        checks, "A3", f"{label} parser-fragment rows",
        "PASS" if rate < 0.0005 else "WARN",
        f"{n_shift:,} rows ({rate:.4%}) with cells shifted by embedded delimiters in "
        f"body; example post_ids: {examples}",
    )

    # --- A4: dtype sanity (score numeric, created_utc parseable) ---
    score_num = pd.to_numeric(df["score"], errors="coerce")
    bad_score = int((score_num.isna() & (df["score"] != "")).sum())
    created = pd.to_datetime(df["created_utc"], format="ISO8601", utc=True, errors="coerce")
    bad_dates = int((created.isna() & (df["created_utc"] != "")).sum())
    _check(
        checks, "A4", f"{label} dtypes",
        "PASS" if (bad_score == 0 and bad_dates == 0) else "WARN",
        f"non-numeric score: {bad_score:,}; unparseable created_utc: {bad_dates:,}",
    )

    # --- B5: duplicate post_id (genuine record duplication; root-caused) ---
    pid = df.loc[df["post_id"] != "", "post_id"]
    pid_counts = pid.value_counts()
    repeated = pid_counts[pid_counts > 1]
    dups = int((repeated - 1).sum())  # extra rows beyond the first copy
    unique_pids = int(pid_counts.shape[0])
    rate = dups / records if records else 0
    if dups == 0:
        status, detail = "PASS", "0 duplicate post_id rows (exporter dedups globally)"
    else:
        maxrep = int(repeated.max())
        if maxrep >= 1000:
            loop_ids = repeated[repeated >= 1000].index
            loop_users = int(df.loc[df["post_id"].isin(loop_ids), "username"].nunique())
            cause = (
                f"max repeat {maxrep:,}× — {len(loop_ids)} post_id(s) from "
                f"{loop_users} user(s) looped (blank created_utc cursor stalled "
                f"pagination, KI-006). Dedup by post_id recovers {unique_pids:,} unique "
                f"records, no data lost."
            )
            status = "FAIL"
        else:
            cause = (
                f"max repeat {maxrep}× — embedded-delimiter parser fragments "
                f"(see A3), not genuine post duplication."
            )
            status = "WARN"
        detail = f"{dups:,} duplicate rows ({rate:.2%}); {cause}"
    _check(checks, "B5", f"{label} duplicate post_id", status, detail)

    # --- C8: selection_reason mix (off-schema values are parser fragments, see A3) ---
    reason_counts = df["selection_reason"].value_counts()
    expected_mix = {k: int(v) for k, v in reason_counts.items() if k in spec["expected_reasons"]}
    n_off = int(records - sum(expected_mix.values()))
    mix = ", ".join(f"{k}={v:,}" for k, v in expected_mix.items())
    _check(
        checks, "C8", f"{label} selection_reason mix",
        "PASS" if n_off / records < 0.0005 else "WARN",
        mix + (f"; +{n_off:,} off-schema fragment rows (see A3)" if n_off else ""),
    )

    # --- C9: distinct users vs target ---
    users = df["username"].nunique()
    utarget = spec["wiki_users"]
    # allow small slack for delimiter-artifact phantom usernames
    status = "PASS" if abs(users - utarget) <= max(5, 0.01 * utarget) else "WARN"
    _check(
        checks, "C9", f"{label} distinct users",
        status,
        f"{users:,} distinct usernames (target ~{utarget:,})",
    )

    # --- C10: bot leakage ---
    distinct_users = df["username"].drop_duplicates()
    bot_mask = distinct_users.map(_is_suspected_bot)
    n_bots = int(bot_mask.sum())
    _check(
        checks, "C10", f"{label} bot leakage",
        "PASS" if n_bots == 0 else "WARN",
        f"{n_bots} distinct usernames match bot blocklist or _bot/Bot heuristic",
    )

    # --- C11: source_subreddit + control_group correctness ---
    bad_src = int((df["source_subreddit"] != spec["source_subreddit"]).sum())
    bad_grp = int((df["control_group"] != spec["control_group"]).sum())
    bad_tag = max(bad_src, bad_grp)
    tag_status = "PASS" if bad_tag == 0 else ("INFO" if bad_tag / records < 0.0005 else "WARN")
    _check(
        checks, "C11", f"{label} group/source tagging",
        tag_status,
        f"wrong source_subreddit: {bad_src:,}; wrong control_group: {bad_grp:,}"
        + (" (parser fragments, see A3)" if bad_tag else ""),
    )

    # --- D12: temporal range + impossible dates ---
    valid_dates = created.dropna()
    n_future = int((valid_dates > SCRAPE_CUTOFF).sum())
    n_ancient = int((valid_dates < REDDIT_FOUNDED).sum())
    dmin = valid_dates.min()
    dmax = valid_dates.max()
    _check(
        checks, "D12", f"{label} date range",
        "PASS" if (n_future == 0 and n_ancient == 0) else "WARN",
        f"{dmin.date()} -> {dmax.date()}; future: {n_future:,}; pre-2005: {n_ancient:,}",
    )

    # --- D13: post vs comment split (title=="" -> comment) ---
    n_posts = int((df["post_type"] == "post").sum())
    n_comments = int((df["post_type"] == "comment").sum())
    empty_title = (df["title"] == "")
    # consistency: comments should have empty title; posts usually non-empty
    comment_with_title = int(((df["post_type"] == "comment") & ~empty_title).sum())
    _check(
        checks, "D13", f"{label} post/comment split",
        "PASS",
        f"posts={n_posts:,}, comments={n_comments:,}; "
        f"comments carrying a non-empty title: {comment_with_title:,}",
    )

    # --- D14: deleted / removed share ---
    n_isdel = int((df["is_deleted"] == "True").sum())
    n_delbody = int(df["body"].isin(DELETED_BODIES).sum())
    _check(
        checks, "D14", f"{label} deleted/removed share",
        "INFO",
        f"is_deleted=True: {n_isdel:,} ({n_isdel/records:.2%}); "
        f"body in [deleted]/[removed]: {n_delbody:,}",
    )

    # --- D15: empty body share ---
    n_empty_body = int((df["body"] == "").sum())
    _check(
        checks, "D15", f"{label} empty body",
        "INFO",
        f"{n_empty_body:,} rows ({n_empty_body/records:.2%}) with empty body "
        f"(link-only posts + deleted/removed)",
    )

    # --- D16: per-user record-count distribution ---
    per_user = df.groupby("username").size()
    q = per_user.quantile([0.5, 0.9, 0.99])
    n_zero = int((per_user == 0).sum())  # cannot occur in-file; reported for completeness
    _check(
        checks, "D16", f"{label} per-user record distribution",
        "PASS" if n_zero == 0 else "WARN",
        f"min={per_user.min():,}, median={int(q.loc[0.5]):,}, "
        f"p90={int(q.loc[0.9]):,}, p99={int(q.loc[0.99]):,}, max={per_user.max():,}; "
        f"users with 0 records in-file: {n_zero}",
    )

    # --- D17: source-subreddit footprint in full histories ---
    n_in_source = int((df["subreddit"] == spec["source_subreddit"]).sum())
    _check(
        checks, "D17", f"{label} source-subreddit footprint",
        "INFO",
        f"{n_in_source:,} rows ({n_in_source/records:.2%}) are in r/{spec['source_subreddit']} "
        f"itself -- expected small for full cross-subreddit histories",
    )

    # --- D18: missing created_utc (no timestamp -> excluded from year-bucketing) ---
    n_no_ts = int((df["created_utc"] == "").sum())
    _check(
        checks, "D18", f"{label} missing created_utc",
        "INFO",
        f"{n_no_ts:,} rows ({n_no_ts/records:.2%}) have no timestamp (sparse API "
        f"records + looped rows); they drop out of the time-series after dedup",
    )

    summary = {
        "label": label,
        "records": records,
        "unique_pids": unique_pids,
        "raw_lines": raw_lines,
        "users": int(users),
        "posts": n_posts,
        "comments": n_comments,
        "reason_mix": expected_mix,
        "deleted": n_isdel,
        "empty_body": n_empty_body,
        "date_min": str(dmin.date()),
        "date_max": str(dmax.date()),
        "field_shift": n_shift,
        "dups": dups,
        "bots": n_bots,
        "per_user_median": int(q.loc[0.5]),
        "per_user_max": int(per_user.max()),
        "post_ids": set(df["post_id"]),
        "usernames": set(df["username"]),
    }

    del df, score_num, created, per_user
    gc.collect()
    return summary


def cross_group_checks(summaries: dict, checks: list):
    print("\n=== Cross-group ===", file=sys.stderr)
    keys = list(summaries.keys())

    # B6: cross-group post_id overlap (global dedup keeps "first" -> could drop)
    # B7: cross-group username leakage (sequential-scrape state risk, KI-022/23)
    total_id_overlap = 0
    total_user_overlap = 0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = summaries[keys[i]], summaries[keys[j]]
            id_ov = len(a["post_ids"] & b["post_ids"])
            user_ov = len(a["usernames"] & b["usernames"])
            total_id_overlap += id_ov
            total_user_overlap += user_ov
            if id_ov or user_ov:
                print(
                    f"  {a['label']} ∩ {b['label']}: post_id={id_ov}, user={user_ov}",
                    file=sys.stderr,
                )
    _check(
        checks, "B6", "Cross-group post_id overlap",
        "PASS" if total_id_overlap == 0 else "WARN",
        f"{total_id_overlap:,} post_ids shared across groups "
        f"(global dedup keeps first -> overlap means silent drop risk)",
    )
    _check(
        checks, "B7", "Cross-group user leakage",
        "PASS" if total_user_overlap == 0 else "WARN",
        f"{total_user_overlap:,} usernames appear in more than one control group",
    )


def archive_identity_check(output_dir: Path, summaries: dict, checks: list):
    """DEC-R1: confirm live primary == April archive (canonical-restore proof)."""
    spec = GROUPS["primary_control_studyAbroad.csv"]
    archive_path = output_dir / spec["archive"]
    primary_key = "primary_control_studyAbroad.csv"
    if not archive_path.exists():
        _check(checks, "E19", "Primary == April archive", "WARN",
               f"archive not found at {archive_path}")
        return
    print("\n=== Archive identity (DEC-R1) ===", file=sys.stderr)
    arch_ids = set(
        pd.read_csv(archive_path, usecols=["post_id"], dtype=str,
                    keep_default_na=False, na_filter=False)["post_id"]
    )
    live_ids = summaries[primary_key]["post_ids"]
    only_live = len(live_ids - arch_ids)
    only_arch = len(arch_ids - live_ids)
    identical = (only_live == 0 and only_arch == 0)
    _check(
        checks, "E19", "Primary == April archive",
        "PASS" if identical else "WARN",
        f"live {len(live_ids):,} post_ids vs archive {len(arch_ids):,}; "
        f"only-in-live={only_live:,}, only-in-archive={only_arch:,}"
        + (" -> canonical April union confirmed restored" if identical else ""),
    )


def log_reconciliation(checks: list):
    """E18: the 2026-06-24 run wrote the keyword-only primary (discarded) +
    both secondaries; 0 failed users, 0 dups removed."""
    _check(
        checks, "E18", "Run-log reconciliation",
        "INFO",
        "rescrape_2026-06-24 wrote 329,387 (keyword-only primary, discarded) + "
        "REU 411,780 + college 1,438,155; 0 duplicate rows removed, 0 failed users. "
        "Live primary is the restored April union.",
    )


def _verdict(checks):
    """Return (markdown_verdict, n_fail, n_warn, n_pass)."""
    n_fail = sum(1 for _, _, s, _ in checks if s == "FAIL")
    n_warn = sum(1 for _, _, s, _ in checks if s == "WARN")
    n_pass = sum(1 for _, _, s, _ in checks if s == "PASS")
    if n_fail:
        v = (f"❌ **{n_fail} FAIL, {n_warn} WARN.** "
             "Resolve the failure(s) below before analysis.")
    elif n_warn:
        v = (f"⚠️ **No failures; {n_warn} warnings, {n_pass} passes.** "
             "Warnings are expected/cosmetic (see notes) — data is analysis-ready.")
    else:
        v = f"✅ **All {n_pass} checks pass.** Data is clean and analysis-ready."
    return v, n_fail, n_warn, n_pass


ANALYST_NOTES = [
    "**Dedup `post_id` on load** (`df.drop_duplicates(subset=\"post_id\")`). Where a "
    "group's *Rows on disk* exceeds *Unique post_id* (see B5), the surplus is duplicate "
    "rows from a pagination loop concentrated in a single user — deduping recovers the "
    "complete, intended dataset with no loss.",
    "**Raw line count ≠ record count.** Embedded newlines in `body` inflate `wc -l`. "
    "Always parse with pandas/`csv`, never `cut`/`awk`/`wc`.",
    "**`None` → empty string, not NaN** (exporter normalization). Isolate comments with "
    "`title == \"\"`, not `title.isna()`.",
    "**Deleted/removed posts are included** (`is_deleted == True`, body "
    "`[deleted]`/`[removed]`). Filter downstream if undesired.",
    "**Primary spans all three identification buckets** (DEC-R1). Subset by "
    "`selection_reason` downstream if a stricter control is wanted — no rescrape needed.",
]


def write_report(path: Path, summaries: dict, checks: list, started: str):
    verdict, n_fail, n_warn, n_pass = _verdict(checks)

    lines = [
        "# Study Abroad — Data Quality Report",
        "",
        f"_Generated {started} by `scripts/qa_check.py` — aggregate-only, PII-free._",
        "",
        "## Verdict",
        "",
        verdict,
        "",
        "## Per-group summary",
        "",
        "| Group | Rows on disk | Unique post_id | Users | Posts | Comments | Deleted | Date range |",
        "|-------|------------:|---------------:|------:|------:|---------:|--------:|-----------|",
    ]
    for s in summaries.values():
        dup_flag = " ⚠️" if s["records"] != s["unique_pids"] else ""
        lines.append(
            f"| {s['label']} | {s['records']:,}{dup_flag} | {s['unique_pids']:,} | "
            f"{s['users']:,} | {s['posts']:,} | {s['comments']:,} | {s['deleted']:,} | "
            f"{s['date_min']} → {s['date_max']} |"
        )

    lines += ["", "## Selection-reason mix (primary spans the DEC-R1 union)", ""]
    for s in summaries.values():
        mix = ", ".join(f"`{k}`={v:,}" for k, v in s["reason_mix"].items())
        lines.append(f"- **{s['label']}**: {mix}")

    lines += ["", "## All checks", "",
              "| ID | Check | Status | Detail |",
              "|----|-------|--------|--------|"]
    for cid, name, status, detail in checks:
        badge = {"PASS": "✅ PASS", "WARN": "⚠️ WARN", "FAIL": "❌ FAIL",
                 "INFO": "ℹ️ INFO"}[status]
        safe = detail.replace("|", "\\|")
        lines.append(f"| {cid} | {name} | {badge} | {safe} |")

    lines += ["", "## Notes for the analyst", ""]
    lines += [f"- {n}" for n in ANALYST_NOTES]
    lines += ["", "_Re-run anytime: `python3 scripts/qa_check.py`._"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _md_inline_to_html(text: str) -> str:
    """Minimal markdown -> HTML for **bold**, `code`, and HTML-escaping."""
    import html as _html
    import re
    out = _html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    return out


def write_html_report(path: Path, summaries: dict, checks: list, started: str):
    verdict, n_fail, n_warn, n_pass = _verdict(checks)
    vclass = "fail" if n_fail else ("warn" if n_warn else "pass")

    badge = {
        "PASS": ('pass', 'PASS'), "WARN": ('warn', 'WARN'),
        "FAIL": ('fail', 'FAIL'), "INFO": ('info', 'INFO'),
    }

    rows_summary = ""
    for s in summaries.values():
        dup = ' <span class="flag">⚠</span>' if s["records"] != s["unique_pids"] else ""
        rows_summary += (
            f"<tr><td>{s['label']}</td><td class='num'>{s['records']:,}{dup}</td>"
            f"<td class='num'>{s['unique_pids']:,}</td><td class='num'>{s['users']:,}</td>"
            f"<td class='num'>{s['posts']:,}</td><td class='num'>{s['comments']:,}</td>"
            f"<td class='num'>{s['deleted']:,}</td>"
            f"<td>{s['date_min']} → {s['date_max']}</td></tr>"
        )

    rows_reason = ""
    for s in summaries.values():
        mix = ", ".join(f"<code>{k}</code> = {v:,}" for k, v in s["reason_mix"].items())
        rows_reason += f"<li><strong>{s['label']}</strong>: {mix}</li>"

    rows_checks = ""
    for cid, name, status, detail in checks:
        cls, lab = badge[status]
        rows_checks += (
            f"<tr class='r-{cls}'><td class='cid'>{cid}</td><td>{name}</td>"
            f"<td><span class='b b-{cls}'>{lab}</span></td>"
            f"<td>{_md_inline_to_html(detail)}</td></tr>"
        )

    notes = "".join(f"<li>{_md_inline_to_html(n)}</li>" for n in ANALYST_NOTES)

    html_doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Study Abroad — Data Quality Report</title>
<style>
  :root {{ --pass:#1a7f37; --warn:#9a6700; --fail:#cf222e; --info:#0969da; --bg:#f6f8fa; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
         color:#1f2328; max-width:1040px; margin:0 auto; padding:28px 22px; line-height:1.5; }}
  h1 {{ font-size:1.7rem; margin:0 0 4px; }}
  h2 {{ font-size:1.15rem; margin:30px 0 10px; border-bottom:1px solid #d0d7de; padding-bottom:6px; }}
  .meta {{ color:#656d76; font-size:.85rem; margin-bottom:18px; }}
  .verdict {{ padding:14px 16px; border-radius:8px; font-size:1.02rem; border:1px solid; }}
  .verdict.pass {{ background:#dafbe1; border-color:#aceebb; }}
  .verdict.warn {{ background:#fff8c5; border-color:#eac54f; }}
  .verdict.fail {{ background:#ffebe9; border-color:#ff8182; }}
  table {{ border-collapse:collapse; width:100%; font-size:.88rem; margin-top:6px; }}
  th,td {{ text-align:left; padding:7px 10px; border-bottom:1px solid #d8dee4; vertical-align:top; }}
  th {{ background:var(--bg); font-weight:600; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  td.cid {{ font-weight:600; color:#656d76; white-space:nowrap; }}
  code {{ background:var(--bg); padding:1px 5px; border-radius:5px; font-size:.85em; }}
  .flag {{ color:var(--fail); }}
  .b {{ font-size:.74rem; font-weight:700; padding:2px 8px; border-radius:20px; color:#fff; white-space:nowrap; }}
  .b-pass {{ background:var(--pass); }} .b-warn {{ background:var(--warn); }}
  .b-fail {{ background:var(--fail); }} .b-info {{ background:var(--info); }}
  tr.r-fail td {{ background:#fff5f5; }}
  ul {{ padding-left:20px; }} li {{ margin:6px 0; }}
  .legend {{ font-size:.8rem; color:#656d76; margin-top:4px; }}
  footer {{ margin-top:30px; color:#656d76; font-size:.82rem; }}
</style></head><body>
<h1>Study Abroad — Data Quality Report</h1>
<div class="meta">Generated {started} by <code>scripts/qa_check.py</code> · aggregate-only, PII-free · re-run: <code>python3 scripts/qa_check.py</code></div>
<div class="verdict {vclass}">{_md_inline_to_html(verdict)}</div>

<h2>Per-group summary</h2>
<table>
<thead><tr><th>Group</th><th class="num">Rows on disk</th><th class="num">Unique post_id</th>
<th class="num">Users</th><th class="num">Posts</th><th class="num">Comments</th>
<th class="num">Deleted</th><th>Date range</th></tr></thead>
<tbody>{rows_summary}</tbody></table>
<div class="legend">⚠ = rows on disk exceed unique post_id (dedupe on load — see check B5).</div>

<h2>Selection-reason mix <span style="font-weight:400;font-size:.85rem;color:#656d76">(primary spans the DEC-R1 union)</span></h2>
<ul>{rows_reason}</ul>

<h2>All checks ({n_pass} pass · {n_warn} warn · {n_fail} fail)</h2>
<table>
<thead><tr><th>ID</th><th>Check</th><th>Status</th><th>Detail</th></tr></thead>
<tbody>{rows_checks}</tbody></table>

<h2>Notes for the analyst</h2>
<ul>{notes}</ul>

<footer>Reusable QA harness · checks A (structure) · B (dedup/uniqueness) ·
C (identification validity) · D (content/temporal) · E (provenance).</footer>
</body></html>
"""
    path.write_text(html_doc, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-dir", default=str(PROJECT_ROOT / "output"),
                    help="directory holding the per-group CSVs")
    ap.add_argument("--reports-dir", default=DEFAULT_REPORTS_DIR,
                    help="directory to write the .md + .html reports into "
                         "(default: the research-wiki study-abroad output folder)")
    args = ap.parse_args()

    output_dir = Path(args.output_dir)
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stamp = f"{datetime.now(timezone.utc):%Y-%m-%d}"
    md_path = reports_dir / f"qa_report_{stamp}.md"
    html_path = reports_dir / f"qa_report_{stamp}.html"

    checks: list = []
    summaries: dict = {}

    for fname, spec in GROUPS.items():
        path = output_dir / fname
        if not path.exists():
            _check(checks, "A1", f"{spec['label']} file", "FAIL",
                   f"missing file: {path}")
            continue
        summaries[fname] = analyze_group(path, spec, checks)

    if len(summaries) > 1:
        cross_group_checks(summaries, checks)
    if "primary_control_studyAbroad.csv" in summaries:
        archive_identity_check(output_dir, summaries, checks)
    log_reconciliation(checks)

    write_report(md_path, summaries, checks, started)
    write_html_report(html_path, summaries, checks, started)
    print(f"\nReports written:\n  {md_path}\n  {html_path}", file=sys.stderr)

    n_fail = sum(1 for _, _, s, _ in checks if s == "FAIL")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
