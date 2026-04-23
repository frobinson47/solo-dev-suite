#!/usr/bin/env python3
"""
list_skills.py -- Phase-aware menu of Solo Dev Suite child skills.

Reads ../data/children.json and prints the child skills filtered by
either a supplied --phase flag or a profile's current_phase. Used by
the orchestrator to show the user what's available right now.

Usage:
    list_skills.py                        # show all, grouped by phase
    list_skills.py --phase build          # show only skills that apply to 'build'
    list_skills.py --slug my-saas      # look up the phase from a profile
    list_skills.py --json                 # machine-readable output

Output defaults to a human-readable grouped table. --json emits an array
of skill objects so callers (including other scripts) can consume it.
"""

from __future__ import annotations

import argparse
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------- #
# Paths                                                                       #
# --------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_DIR = SCRIPT_DIR.parent
CHILDREN_PATH = SUITE_DIR / "data" / "children.json"
PROFILES_DIR = SUITE_DIR / "profiles"

# Canonical phase order. If you add a phase, update this tuple AND the
# enum in templates/profile.schema.json — they must stay in sync or the
# validator will reject profiles using the new phase.
PHASES = ("idea", "scope", "architecture", "build", "ship", "grow", "sustain")


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _err(msg: str) -> None:
    print(f"[list_skills] {msg}", file=sys.stderr)


def _load_children() -> List[Dict[str, Any]]:
    """Load and return the children array from children.json."""
    if not CHILDREN_PATH.exists():
        _err(f"Registry not found at {CHILDREN_PATH}.")
        sys.exit(2)
    try:
        data = json.loads(CHILDREN_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _err(f"Registry is invalid JSON: {e}")
        sys.exit(2)
    return data.get("children", [])


def _load_profile_phase(slug: str) -> Optional[str]:
    """Get the current_phase from a profile file. Returns None if missing."""
    path = PROFILES_DIR / f"{slug}.json"
    if not path.exists():
        _err(f"No profile for slug '{slug}'.")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("current_phase")
    except json.JSONDecodeError as e:
        _err(f"Profile {path} is corrupted: {e}")
        return None


def _status_icon(status: str) -> str:
    """Map status string → display icon. Keeps the table visually scannable."""
    return {"active": "[x]", "planned": "[ ]", "deprecated": "[!]"}.get(status, "[?]")


# --------------------------------------------------------------------------- #
# Filtering                                                                   #
# --------------------------------------------------------------------------- #

def filter_by_phase(children: List[Dict[str, Any]], phase: str) -> List[Dict[str, Any]]:
    """Return only the children whose `phases` array contains `phase`."""
    return [c for c in children if phase in c.get("phases", [])]


# --------------------------------------------------------------------------- #
# Rendering                                                                   #
# --------------------------------------------------------------------------- #

def render_table(children: List[Dict[str, Any]], heading: str) -> None:
    """Render a single flat table of children. Used for phase-filtered output."""
    if not children:
        print(f"\n  {heading}")
        print("  No skills match this phase.\n")
        return

    rows = [
        {
            "icon": _status_icon(c.get("status", "")),
            "name": c["name"],
            "phases": ", ".join(c.get("phases", [])),
            "description": c.get("description", ""),
        }
        for c in children
    ]
    # Dynamic column widths so long names don't wrap mid-table.
    name_w = max(len("skill"), *(len(r["name"]) for r in rows))
    phases_w = max(len("phase(s)"), *(len(r["phases"]) for r in rows))

    print(f"\n  {heading}")
    print(f"  {'-' * len(heading)}")
    print(f"     {'skill'.ljust(name_w)}  {'phase(s)'.ljust(phases_w)}  description")
    print(f"     {'-' * name_w}  {'-' * phases_w}  -----------")
    for r in rows:
        print(f"  {r['icon']}  {r['name'].ljust(name_w)}  {r['phases'].ljust(phases_w)}  {r['description']}")
    print()


def render_grouped(children: List[Dict[str, Any]]) -> None:
    """Group all children under their primary phases. Used when no filter is given."""
    print()
    for phase in PHASES:
        matching = filter_by_phase(children, phase)
        if not matching:
            continue
        print(f"  {phase.upper()}")
        print(f"  {'-' * len(phase)}")
        for c in matching:
            icon = _status_icon(c.get("status", ""))
            print(f"    {icon}  {c['name']:<25} {c.get('description', '')}")
        print()


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="List Solo Dev Suite child skills, optionally filtered by phase."
    )
    # Mutually exclusive filter sources — either a raw phase or a profile slug.
    # If both are given, --phase wins and we warn.
    parser.add_argument("--phase", choices=PHASES, help="Filter to this phase only.")
    parser.add_argument("--slug", help="Use this profile's current_phase as the filter.")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    args = parser.parse_args(argv)

    children = _load_children()
    phase: Optional[str] = None

    if args.phase:
        phase = args.phase
        if args.slug:
            _err("Both --phase and --slug given; --phase wins.")
    elif args.slug:
        phase = _load_profile_phase(args.slug)
        if phase is None:
            return 3

    if phase is not None:
        filtered = filter_by_phase(children, phase)
        if args.json:
            print(json.dumps(filtered, indent=2))
        else:
            render_table(filtered, f"Skills for phase: {phase}")
    else:
        if args.json:
            print(json.dumps(children, indent=2))
        else:
            render_grouped(children)

    return 0


if __name__ == "__main__":
    sys.exit(main())
