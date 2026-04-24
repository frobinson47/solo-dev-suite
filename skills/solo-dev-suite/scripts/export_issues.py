#!/usr/bin/env python3
"""
export_issues.py -- Export skill outputs to issue trackers (GitHub/Forgejo).

Reads sidecar files for a project and creates issues in the configured
issue tracker. Supports GitHub and Forgejo APIs. Idempotent: tracks
exported items to prevent duplicates on re-run.

Commands:
    export  <slug> --target <github|forgejo> --repo <owner/repo> --token <token>
                   [--url <api-base>] [--skills <scope,techdebt,...>] [--dry-run]
    status  <slug>                           # show what's been exported

Exit codes:
    0  success
    1  slug/profile not found
    2  suite install broken
    3  API error
    4  no items to export
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_DIR = SCRIPT_DIR.parent
PROFILES_DIR = SUITE_DIR / "profiles"

# Skill names → sidecar suffixes
EXPORTABLE_SKILLS = {
    "scope": "scope",
    "techdebt": "techdebt",
    "security": "security",
    "sprint": "sprint",
}

# Default API base URLs
API_BASES = {
    "github": "https://api.github.com",
    "forgejo": None,  # must be provided via --url
}


def _err(msg: str) -> None:
    print(f"[export_issues] {msg}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Tracking file — prevents duplicate exports                                  #
# --------------------------------------------------------------------------- #

def _tracking_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.exported.json"


def _load_tracking(slug: str) -> Dict[str, Any]:
    path = _tracking_path(slug)
    if not path.exists():
        return {"slug": slug, "exports": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"slug": slug, "exports": {}}


def _save_tracking(slug: str, data: Dict[str, Any]) -> None:
    path = _tracking_path(slug)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# Sidecar readers — extract exportable items                                  #
# --------------------------------------------------------------------------- #

ExportItem = Dict[str, Any]  # {id, title, body, labels[], priority, skill}


def _read_scope(slug: str) -> List[ExportItem]:
    """Extract scope items that should become issues."""
    path = PROFILES_DIR / f"{slug}.scope.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = []
    buckets = data.get("buckets", {})

    for item in buckets.get("launch_blocking", []):
        items.append({
            "id": item["id"],
            "title": f"[Scope] {item['name']}",
            "body": (
                f"**Bucket:** Launch-blocking\n"
                f"**Effort:** {item.get('effort', '?')}\n"
                f"**Impact:** {item.get('impact', '?')}\n\n"
                f"{item.get('rationale', '')}\n\n"
                f"_Exported from Solo Dev Suite scope guardian_"
            ),
            "labels": ["scope", "launch-blocking"],
            "priority": "high",
            "skill": "scope",
        })

    for item in buckets.get("post_launch_v1", []):
        items.append({
            "id": item["id"],
            "title": f"[Scope] {item['name']}",
            "body": (
                f"**Bucket:** Post-launch ({item.get('target_wave', 'v1.1')})\n\n"
                f"{item.get('description', '')}\n\n"
                f"_Exported from Solo Dev Suite scope guardian_"
            ),
            "labels": ["scope", "post-launch"],
            "priority": "medium",
            "skill": "scope",
        })

    return items


def _read_techdebt(slug: str) -> List[ExportItem]:
    """Extract open tech debt items."""
    path = PROFILES_DIR / f"{slug}.techdebt.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = []

    for item in data.get("items", []):
        if item.get("status") in ("paid-down",):
            continue
        categories = ", ".join(item.get("categories", []))
        items.append({
            "id": item["id"],
            "title": f"[Tech Debt] {item['title']}",
            "body": (
                f"**Categories:** {categories}\n"
                f"**Impact:** {item.get('impact', '?')}\n"
                f"**Effort:** {item.get('effort', '?')}\n"
                f"**Urgency:** {item.get('urgency_window', '?')}\n"
                f"**Status:** {item.get('status', 'open')}\n\n"
                f"{item.get('description', '')}\n\n"
                f"{item.get('notes', '')}\n\n"
                f"_Exported from Solo Dev Suite tech debt register_"
            ),
            "labels": ["tech-debt"] + item.get("categories", [])[:2],
            "priority": item.get("impact", "medium"),
            "skill": "techdebt",
        })

    return items


def _read_security(slug: str) -> List[ExportItem]:
    """Extract failed/unchecked security findings."""
    path = PROFILES_DIR / f"{slug}.security.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = []

    for cat in data.get("categories", []):
        if not cat.get("applicable", True):
            continue
        cat_name = cat.get("name", cat.get("id", "unknown"))
        for item in cat.get("items", []):
            status = item.get("status", "not-checked")
            if status in ("passed", "not-applicable"):
                continue
            severity = item.get("severity", "medium")
            status_label = "accepted-risk" if status == "accepted-risk" else "open"
            items.append({
                "id": item["id"],
                "title": f"[Security] {item['name']}",
                "body": (
                    f"**Category:** {cat_name}\n"
                    f"**Severity:** {severity}\n"
                    f"**Status:** {status_label}\n\n"
                    f"{item.get('notes', '')}\n"
                    f"{('**Risk rationale:** ' + item['risk_rationale']) if item.get('risk_rationale') else ''}\n\n"
                    f"_Exported from Solo Dev Suite security audit_"
                ),
                "labels": ["security", f"severity:{severity}"],
                "priority": severity,
                "skill": "security",
            })

    return items


def _read_sprint(slug: str) -> List[ExportItem]:
    """Extract backlog items and active sprint TODO items."""
    path = PROFILES_DIR / f"{slug}.sprint.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = []

    for item in data.get("backlog", []):
        items.append({
            "id": item["id"],
            "title": f"[Backlog] {item['title']}",
            "body": (
                f"**Priority:** {item.get('priority', '?')}\n"
                f"**Category:** {item.get('category', '?')}\n"
                f"**Estimate:** {item.get('estimate_hours', '?')}h\n\n"
                f"{item.get('description', '')}\n\n"
                f"_Exported from Solo Dev Suite sprint planner_"
            ),
            "labels": ["backlog", item.get("category", "feature")],
            "priority": item.get("priority", "medium"),
            "skill": "sprint",
        })

    for sprint in data.get("sprints", []):
        if sprint.get("status") == "completed":
            continue
        for item in sprint.get("items", []):
            if item.get("status") in ("done", "dropped"):
                continue
            items.append({
                "id": item["id"],
                "title": f"[Sprint] {item['title']}",
                "body": (
                    f"**Sprint:** {sprint.get('id', '?')} ({sprint.get('goal', '')})\n"
                    f"**Status:** {item.get('status', 'todo')}\n"
                    f"**Estimate:** {item.get('estimate_hours', '?')}h\n"
                    f"**Category:** {item.get('category', '?')}\n\n"
                    f"{item.get('description', '')}\n\n"
                    f"_Exported from Solo Dev Suite sprint planner_"
                ),
                "labels": ["sprint", item.get("category", "feature")],
                "priority": "high",
                "skill": "sprint",
            })

    return items


READERS = {
    "scope": _read_scope,
    "techdebt": _read_techdebt,
    "security": _read_security,
    "sprint": _read_sprint,
}


# --------------------------------------------------------------------------- #
# Issue tracker API                                                           #
# --------------------------------------------------------------------------- #

def _api_request(
    method: str, url: str, token: str, data: Optional[Dict] = None
) -> Tuple[int, Any]:
    """Make an HTTP request to the issue tracker API."""
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body_text)
        except json.JSONDecodeError:
            return e.code, {"error": body_text}


def _create_issue(
    api_base: str, repo: str, token: str, title: str, body: str, labels: List[str]
) -> Tuple[bool, Optional[int], str]:
    """Create an issue via the API. Returns (success, issue_number, url)."""
    url = f"{api_base}/repos/{repo}/issues"
    status, resp = _api_request("POST", url, token, {
        "title": title,
        "body": body,
        "labels": labels,
    })
    if status in (200, 201):
        return True, resp.get("number"), resp.get("html_url", "")
    return False, None, resp.get("message", str(resp))


def _ensure_labels(api_base: str, repo: str, token: str, labels: List[str]) -> None:
    """Create labels that don't exist yet. Best-effort, no failure on conflict."""
    # Fetch existing labels
    url = f"{api_base}/repos/{repo}/labels?limit=100"
    status, existing = _api_request("GET", url, token)
    if status != 200:
        return
    existing_names = {l["name"] for l in existing}

    # Color palette for auto-created labels
    colors = {
        "scope": "0075ca",
        "launch-blocking": "d73a4a",
        "post-launch": "a2eeef",
        "tech-debt": "e4e669",
        "security": "b60205",
        "backlog": "c5def5",
        "sprint": "1d76db",
        "severity:critical": "b60205",
        "severity:high": "d93f0b",
        "severity:medium": "fbca04",
        "severity:low": "0e8a16",
    }

    for label in labels:
        if label not in existing_names:
            color = colors.get(label, "ededed")
            _api_request("POST", f"{api_base}/repos/{repo}/labels", token, {
                "name": label,
                "color": f"#{color}",
            })


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_export(args: argparse.Namespace) -> int:
    """Export skill items to the issue tracker."""
    slug = args.slug
    target = args.target
    repo = args.repo
    token = args.token
    dry_run = args.dry_run
    skills_filter = [s.strip() for s in args.skills.split(",")] if args.skills else list(READERS.keys())

    # Validate target
    if target == "forgejo" and not args.url:
        _err("--url is required for Forgejo (e.g. https://forgejo.example.com/api/v1)")
        return 2
    api_base = args.url if args.url else API_BASES.get(target, "")

    # Check profile exists
    profile_path = PROFILES_DIR / f"{slug}.json"
    if not profile_path.exists():
        _err(f"No profile for slug '{slug}'.")
        return 1

    # Collect all items from selected skills
    all_items: List[ExportItem] = []
    for skill in skills_filter:
        reader = READERS.get(skill)
        if reader is None:
            _err(f"Unknown skill '{skill}'. Available: {', '.join(READERS.keys())}")
            continue
        items = reader(slug)
        all_items.extend(items)

    if not all_items:
        print(f"  No exportable items found for '{slug}'.")
        return 4

    # Load tracking to skip already-exported items
    tracking = _load_tracking(slug)
    exports = tracking.get("exports", {})
    new_items = [i for i in all_items if i["id"] not in exports]

    if not new_items:
        print(f"  All {len(all_items)} items already exported. Nothing to do.")
        return 0

    print(f"\n  Exporting {len(new_items)} items for '{slug}' to {target} ({repo})")
    if dry_run:
        print(f"  [DRY RUN] No issues will be created.\n")

    # Ensure labels exist
    all_labels = set()
    for item in new_items:
        all_labels.update(item["labels"])
    if not dry_run:
        _ensure_labels(api_base, repo, token, list(all_labels))

    # Create issues
    created = 0
    errors = 0
    for item in new_items:
        if dry_run:
            print(f"  [DRY] #{item['id']}  {item['title']}")
            print(f"         Labels: {', '.join(item['labels'])}")
            created += 1
            continue

        ok, issue_num, url_or_err = _create_issue(
            api_base, repo, token, item["title"], item["body"], item["labels"]
        )
        if ok:
            print(f"  Created: #{issue_num}  {item['title']}")
            exports[item["id"]] = {
                "issue_number": issue_num,
                "url": url_or_err,
                "exported_at": _now_iso(),
                "target": target,
                "repo": repo,
            }
            created += 1
        else:
            _err(f"Failed to create issue for {item['id']}: {url_or_err}")
            errors += 1

    # Save tracking
    if not dry_run:
        tracking["exports"] = exports
        tracking["last_export"] = _now_iso()
        tracking["target"] = target
        tracking["repo"] = repo
        _save_tracking(slug, tracking)

    print(f"\n  Summary: {created} created, {errors} errors, "
          f"{len(all_items) - len(new_items)} already exported.\n")

    return 3 if errors > 0 else 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show export status for a project."""
    slug = args.slug
    tracking = _load_tracking(slug)
    exports = tracking.get("exports", {})

    if not exports:
        print(f"\n  No exports recorded for '{slug}'.\n")
        return 0

    if args.json:
        print(json.dumps(tracking, indent=2))
        return 0

    print(f"\n  Export status for '{slug}'")
    print(f"  Target: {tracking.get('target', '?')} ({tracking.get('repo', '?')})")
    print(f"  Last export: {tracking.get('last_export', '?')}")
    print(f"  Total exported: {len(exports)}\n")

    # Group by skill
    by_skill: Dict[str, List] = {}
    for item_id, info in exports.items():
        # Infer skill from ID prefix
        skill = "unknown"
        if item_id.startswith(("LB", "PL", "PK", "WB")):
            skill = "scope"
        elif item_id.startswith("TD"):
            skill = "techdebt"
        elif item_id.startswith(("SEC", "AUTH", "INP", "TRN", "API", "FE", "INF", "DEP", "DAT", "INT")):
            skill = "security"
        elif item_id.startswith(("BL", "SI")):
            skill = "sprint"
        by_skill.setdefault(skill, []).append((item_id, info))

    for skill, items in sorted(by_skill.items()):
        print(f"  {skill} ({len(items)} items):")
        for item_id, info in items:
            print(f"    {item_id} -> #{info.get('issue_number', '?')} ({info.get('exported_at', '?')})")
        print()

    return 0


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="export_issues",
        description="Export Solo Dev Suite skill outputs to issue trackers.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="Export items to an issue tracker.")
    p_export.add_argument("slug", help="Project slug.")
    p_export.add_argument("--target", required=True, choices=["github", "forgejo"],
                          help="Issue tracker type.")
    p_export.add_argument("--repo", required=True,
                          help="Repository (owner/repo).")
    p_export.add_argument("--token", required=True,
                          help="API token with issue write permissions.")
    p_export.add_argument("--url",
                          help="API base URL (required for Forgejo, e.g. https://forgejo.example.com/api/v1).")
    p_export.add_argument("--skills",
                          help="Comma-separated skills to export (default: all). "
                               f"Available: {', '.join(READERS.keys())}")
    p_export.add_argument("--dry-run", action="store_true",
                          help="Show what would be exported without creating issues.")
    p_export.set_defaults(func=cmd_export)

    p_status = sub.add_parser("status", help="Show export status.")
    p_status.add_argument("slug", help="Project slug.")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
