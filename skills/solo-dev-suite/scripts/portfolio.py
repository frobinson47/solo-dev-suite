#!/usr/bin/env python3
"""
portfolio.py -- Portfolio view across all Solo Dev Suite project profiles.

Compares all registered projects side-by-side: phase, staleness, blockers,
third-party risk, launch proximity, and skill coverage. Sorts by urgency
so the project that needs attention most is at the top.

Commands:
    view    [--json]    # side-by-side comparison table
    health  <slug>      # detailed health breakdown for one project

Exit codes:
    0  success
    1  no profiles found
    2  suite install broken (missing files)
    3  slug not found

Design notes:
  * No external deps. Pure stdlib. Same patterns as profile_io.py.
  * Health score is 0-100. Higher = healthier. Computed from:
    - Phase progression (idea=10, scope=20, ..., sustain=70)
    - Staleness penalty (days since last skill run)
    - Blocker penalty (per active blocker)
    - Risk penalty (high/critical third-party services without fallback)
    - Skill coverage bonus (% of phase-relevant skills that have been run)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_DIR = SCRIPT_DIR.parent
PROFILES_DIR = SUITE_DIR / "profiles"
CHILDREN_PATH = SUITE_DIR / "data" / "children.json"

PHASE_ORDER = ["idea", "scope", "architecture", "build", "ship", "grow", "sustain"]
PHASE_SCORE = {p: (i + 1) * 10 for i, p in enumerate(PHASE_ORDER)}


def _err(msg: str) -> None:
    print(f"[portfolio] {msg}", file=sys.stderr)


def _load_children() -> List[Dict[str, Any]]:
    """Load child skill definitions for phase mapping."""
    if not CHILDREN_PATH.exists():
        return []
    try:
        data = json.loads(CHILDREN_PATH.read_text(encoding="utf-8"))
        return data.get("children", [])
    except (json.JSONDecodeError, KeyError):
        return []


def _skills_for_phase(phase: str, children: List[Dict[str, Any]]) -> List[str]:
    """Return skill names relevant to a given phase."""
    return [c["name"] for c in children if phase in c.get("phases", [])]


def _days_since(iso_ts: str) -> Optional[int]:
    """Days between an ISO timestamp and now. Returns None if unparseable."""
    try:
        dt = datetime.fromisoformat(iso_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None


def _days_until(date_str: str) -> Optional[int]:
    """Days until a YYYY-MM-DD date. Negative = past due."""
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        delta = target - datetime.now(timezone.utc)
        return delta.days
    except (ValueError, TypeError):
        return None


def _compute_health(profile: Dict[str, Any], children: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute a health breakdown for one profile."""
    phase = profile.get("current_phase", "idea")
    last_runs = profile.get("last_skill_run", {})
    blockers = profile.get("blockers", [])
    services = profile.get("third_party_services", [])
    launch_date = profile.get("launch_target_date")

    # Base score from phase
    base = PHASE_SCORE.get(phase, 10)

    # Staleness: days since any skill was last run
    staleness_days = None
    if last_runs:
        days_list = [_days_since(ts) for ts in last_runs.values()]
        valid = [d for d in days_list if d is not None]
        if valid:
            staleness_days = min(valid)  # most recent run

    staleness_penalty = 0
    if staleness_days is None:
        staleness_penalty = 20  # never run any skill
    elif staleness_days > 30:
        staleness_penalty = 15
    elif staleness_days > 14:
        staleness_penalty = 10
    elif staleness_days > 7:
        staleness_penalty = 5

    # Blockers
    blocker_penalty = min(len(blockers) * 5, 20)

    # Unhedged risk: high/critical services with no fallback
    unhedged = [s for s in services
                if s.get("risk_level") in ("high", "critical")
                and not s.get("fallback")]
    risk_penalty = min(len(unhedged) * 5, 15)

    # Skill coverage: % of phase-relevant skills that have been run
    relevant = _skills_for_phase(phase, children)
    if relevant:
        covered = sum(1 for s in relevant if s in last_runs)
        coverage_pct = int(covered / len(relevant) * 100)
        coverage_bonus = int(coverage_pct * 0.15)  # max 15 points
    else:
        coverage_pct = 100
        coverage_bonus = 15

    # Launch proximity urgency
    launch_days = _days_until(launch_date) if launch_date else None
    launch_flag = None
    if launch_days is not None:
        if launch_days < 0:
            launch_flag = "OVERDUE"
        elif launch_days <= 7:
            launch_flag = "THIS WEEK"
        elif launch_days <= 30:
            launch_flag = f"{launch_days}d"

    score = max(0, min(100, base - staleness_penalty - blocker_penalty - risk_penalty + coverage_bonus))

    return {
        "score": score,
        "phase": phase,
        "staleness_days": staleness_days,
        "staleness_penalty": staleness_penalty,
        "blockers": len(blockers),
        "blocker_penalty": blocker_penalty,
        "unhedged_risks": len(unhedged),
        "risk_penalty": risk_penalty,
        "coverage_pct": coverage_pct,
        "coverage_bonus": coverage_bonus,
        "launch_days": launch_days,
        "launch_flag": launch_flag,
        "skills_run": len(last_runs),
        "skills_relevant": len(relevant),
    }


def _load_all_profiles() -> List[Dict[str, Any]]:
    """Load all profiles with computed health data."""
    if not PROFILES_DIR.exists():
        return []

    children = _load_children()
    results = []

    for p in sorted(PROFILES_DIR.glob("*.json")):
        if p.stem == "example":
            continue  # skip the template
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _err(f"Skipping corrupted profile: {p.name}")
            continue

        health = _compute_health(data, children)
        results.append({
            "slug": data.get("project_slug", p.stem),
            "name": data.get("project_name", "?"),
            "phase": data.get("current_phase", "?"),
            "type": data.get("project_type", "?"),
            "hours_week": data.get("available_hours_per_week", 0),
            "blockers": len(data.get("blockers", [])),
            "services": len(data.get("third_party_services", [])),
            "launch_target": data.get("launch_target_date"),
            "updated_at": data.get("updated_at", "?"),
            "health": health,
        })

    # Sort by urgency: lowest health score first (needs most attention)
    results.sort(key=lambda r: r["health"]["score"])
    return results


def _health_indicator(score: int) -> str:
    """Return a text health indicator."""
    if score >= 70:
        return f"{score} OK"
    elif score >= 40:
        return f"{score} WARN"
    else:
        return f"{score} CRIT"


def cmd_view(args: argparse.Namespace) -> int:
    """Side-by-side portfolio comparison."""
    profiles = _load_all_profiles()
    if not profiles:
        if args.json:
            print("[]")
        else:
            print("No profiles found. Create one with the solo-dev-suite orchestrator.")
        return 1

    if args.json:
        print(json.dumps(profiles, indent=2))
        return 0

    headers = ["slug", "phase", "health", "blockers", "coverage", "launch", "updated"]
    rows = []
    for p in profiles:
        h = p["health"]
        launch_col = h["launch_flag"] or (p["launch_target"] or "-")
        rows.append({
            "slug": p["slug"],
            "phase": p["phase"],
            "health": _health_indicator(h["score"]),
            "blockers": str(h["blockers"]) if h["blockers"] else "-",
            "coverage": f"{h['coverage_pct']}% ({h['skills_run']}/{h['skills_relevant']})",
            "launch": launch_col,
            "updated": p["updated_at"][:10] if p["updated_at"] != "?" else "?",
        })

    widths = {h: max(len(h), *(len(str(r[h])) for r in rows)) for h in headers}
    header_line = "  ".join(h.ljust(widths[h]) for h in headers)

    print(f"\n  Portfolio ({len(rows)} projects, sorted by urgency)\n")
    print(f"  {header_line}")
    print(f"  {'  '.join('-' * widths[h] for h in headers)}")
    for r in rows:
        print("  " + "  ".join(str(r[h]).ljust(widths[h]) for h in headers))
    print()
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Detailed health breakdown for one project."""
    path = PROFILES_DIR / f"{args.slug}.json"
    if not path.exists():
        _err(f"No profile found for slug '{args.slug}'.")
        return 3

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _err(f"Profile corrupted: {path}")
        return 2

    children = _load_children()
    h = _compute_health(data, children)

    if args.json:
        print(json.dumps({"slug": args.slug, "health": h}, indent=2))
        return 0

    print(f"\n  Health: {data.get('project_name', args.slug)}  ({args.slug})")
    print(f"  {'=' * 50}")
    print(f"  Overall score   : {_health_indicator(h['score'])}")
    print(f"  Phase           : {h['phase']}")
    print()
    print(f"  Staleness       : {h['staleness_days'] or 'never run'}d since last skill run  (-{h['staleness_penalty']})")
    print(f"  Blockers        : {h['blockers']} active  (-{h['blocker_penalty']})")
    print(f"  Unhedged risks  : {h['unhedged_risks']} high/critical services without fallback  (-{h['risk_penalty']})")
    print(f"  Skill coverage  : {h['coverage_pct']}% of phase-relevant skills run  (+{h['coverage_bonus']})")

    if h["launch_flag"]:
        print(f"  Launch          : {h['launch_flag']}")
    elif data.get("launch_target_date"):
        days = h["launch_days"]
        print(f"  Launch          : {data['launch_target_date']} ({days}d away)")
    else:
        print(f"  Launch          : no target date set")

    # Show which phase-relevant skills have/haven't been run
    relevant = _skills_for_phase(h["phase"], children)
    last_runs = data.get("last_skill_run", {})
    if relevant:
        print(f"\n  Phase-relevant skills ({h['phase']}):")
        for s in sorted(relevant):
            status = last_runs.get(s, None)
            if status:
                days = _days_since(status)
                print(f"    [x] {s:<25} last run {days}d ago")
            else:
                print(f"    [ ] {s:<25} never run")

    print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portfolio",
        description="Portfolio view across all Solo Dev Suite project profiles.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_view = sub.add_parser("view", help="Side-by-side comparison of all projects.")
    p_view.add_argument("--json", action="store_true", help="Machine-readable output.")
    p_view.set_defaults(func=cmd_view)

    p_health = sub.add_parser("health", help="Detailed health breakdown for one project.")
    p_health.add_argument("slug", help="Project slug.")
    p_health.add_argument("--json", action="store_true", help="Machine-readable output.")
    p_health.set_defaults(func=cmd_health)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
