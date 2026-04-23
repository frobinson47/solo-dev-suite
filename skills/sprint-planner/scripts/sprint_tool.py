#!/usr/bin/env python3
"""
sprint_tool.py -- Solo-dev sprint planner for the sprint-planner skill.

Converts a backlog into realistic sprints accounting for day job, family,
and surprise maintenance. Uses available_hours_per_week and launch_target_date
from the project profile for capacity math.

Owns:
  * The per-project sidecar at solo-dev-suite/profiles/<slug>.sprint.json
  * The profile mirror at profile.sprint_model (updated on every write)
  * The rendered SPRINT_PLAN.md doc

Commands:
    init     <slug> --from-stdin          # Set up capacity + initial backlog
    add      <slug> --from-stdin          # Add item(s) to backlog
    plan     <slug> --from-stdin          # Plan next sprint from backlog
    start    <slug>                       # Activate the next planned sprint
    update   <slug> --from-stdin          # Update item statuses in active sprint
    complete <slug> [--retro <notes>]     # Complete the active sprint
    show     <slug> [--json]              # Display current state
    render   <slug>                       # Generate SPRINT_PLAN.md
    delete   <slug> [--yes]               # Remove sidecar

Design notes:
  * Sprint IDs are SP01, SP02, ... (monotonic, never recycled).
  * Sprint item IDs are SI01, SI02, ... (global across all sprints + backlog).
  * Backlog item IDs are BL01, BL02, ... (converted to SI## when moved to sprint).
  * Velocity is tracked as completed hours per sprint. Average velocity
    over completed sprints informs "can you make launch?" math.
  * Buffer percent accounts for interrupts (day job fires, family, infra).
    Default 20% -- honest beats optimistic every time.
  * Launch countdown compares remaining backlog hours against remaining
    sprints before launch_target_date. Red/yellow/green signal.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


# --------------------------------------------------------------------------- #
# Path discovery                                                              #
# --------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent       # .../sprint-planner/scripts
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
SCHEMA_PATH = TEMPLATES_DIR / "sprint.schema.json"
SPRINT_MD_TMPL = TEMPLATES_DIR / "SPRINT_PLAN.md.tmpl"


def _find_suite_dir() -> Path:
    """Locate solo-dev-suite. Env var wins; otherwise walk up looking for sibling."""
    env = os.environ.get("SOLO_DEV_SUITE_DIR")
    if env:
        p = Path(env).resolve()
        if p.is_dir():
            return p
    sibling = SKILL_DIR.parent / "solo-dev-suite"
    if sibling.is_dir():
        return sibling
    for ancestor in SKILL_DIR.parents:
        candidate = ancestor / "solo-dev-suite"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "Could not find solo-dev-suite directory. "
        "Set SOLO_DEV_SUITE_DIR env var or place the suite as a sibling of this skill."
    )


SUITE_DIR = _find_suite_dir()
PROFILES_DIR = SUITE_DIR / "profiles"


# --------------------------------------------------------------------------- #
# Small utilities                                                             #
# --------------------------------------------------------------------------- #

def _err(msg: str) -> None:
    print(f"[sprint_tool] {msg}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _profile_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.json"


def _sprint_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.sprint.json"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _err(f"{path} is corrupted: {e}")
        sys.exit(3)


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_stdin_json() -> Dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        _err("Expected JSON on stdin, got nothing.")
        sys.exit(5)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        _err(f"stdin is not valid JSON: {e}")
        sys.exit(5)
    if not isinstance(obj, dict):
        _err(f"stdin JSON must be an object, got {type(obj).__name__}.")
        sys.exit(5)
    return obj


# --------------------------------------------------------------------------- #
# JSON Schema validation (inline, self-contained)                             #
# --------------------------------------------------------------------------- #

def _type_matches(value: Any, type_spec: Any) -> bool:
    type_map = {
        "string": str, "integer": int, "number": (int, float),
        "array": list, "object": dict, "boolean": bool, "null": type(None),
    }
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    for t in types:
        py = type_map.get(t)
        if py is None:
            continue
        if t == "integer" and isinstance(value, bool):
            continue
        if isinstance(value, py):
            return True
    return False


def _validate_value(value: Any, schema: Dict[str, Any], path: str, errors: List[str]) -> None:
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {value!r}")
        return
    if "type" in schema and not _type_matches(value, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']}, got {type(value).__name__}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")
        return
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: length {len(value)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: length {len(value)} > maxLength {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match pattern {schema['pattern']!r}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: {len(value)} items < minItems {schema['minItems']}")
        if "items" in schema:
            for i, item in enumerate(value):
                _validate_value(item, schema["items"], f"{path}[{i}]", errors)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required property '{req}'")
        additional = schema.get("additionalProperties", True)
        for k, v in value.items():
            sub_path = f"{path}.{k}" if path else k
            if k in props:
                _validate_value(v, props[k], sub_path, errors)
            else:
                if additional is False:
                    errors.append(f"{path}: unknown property '{k}'")
                elif isinstance(additional, dict):
                    _validate_value(v, additional, sub_path, errors)


def _validate_sidecar(data: Dict[str, Any]) -> List[str]:
    if not SCHEMA_PATH.exists():
        _err(f"Schema not found at {SCHEMA_PATH}. Skill install is broken.")
        sys.exit(2)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors: List[str] = []
    _validate_value(data, schema, "", errors)
    return errors


# --------------------------------------------------------------------------- #
# Profile + sidecar helpers                                                   #
# --------------------------------------------------------------------------- #

def _load_profile(slug: str) -> Dict[str, Any]:
    profile = _read_json(_profile_path(slug))
    if profile is None:
        _err(f"No profile found for '{slug}'. Run profile_io.py init first.")
        sys.exit(8)
    return profile


def _load_sidecar(slug: str) -> Dict[str, Any]:
    data = _read_json(_sprint_path(slug))
    if data is None:
        _err(f"No sprint sidecar found for '{slug}'. Run 'init' first.")
        sys.exit(10)
    return data


def _write_sidecar(slug: str, data: Dict[str, Any]) -> None:
    data["updated_at"] = _now_iso()
    errors = _validate_sidecar(data)
    if errors:
        _err("Sidecar validation failed:")
        for e in errors:
            _err(f"  - {e}")
        sys.exit(4)
    _write_json_atomic(_sprint_path(slug), data)


def _mirror_to_profile(slug: str, sidecar: Dict[str, Any]) -> None:
    """Write lean sprint summary to profile + update last_skill_run."""
    profile = _load_profile(slug)

    # Compute velocity average from completed sprints.
    completed = [s for s in sidecar["sprints"] if s["status"] == "completed"]
    velocities = [s["velocity_hours"] for s in completed if s.get("velocity_hours") is not None]
    avg_velocity = round(sum(velocities) / len(velocities), 1) if velocities else None

    active = _get_active_sprint(sidecar)
    backlog_hours = sum(b["estimate_hours"] for b in sidecar["backlog"])

    profile["sprint_model"] = {
        "total_sprints": len(sidecar["sprints"]),
        "completed_sprints": len(completed),
        "active_sprint_id": active["id"] if active else None,
        "backlog_items": len(sidecar["backlog"]),
        "backlog_hours": backlog_hours,
        "avg_velocity_hours": avg_velocity,
        "effective_hours_per_sprint": sidecar["capacity"]["effective_hours_per_sprint"],
    }
    profile.setdefault("last_skill_run", {})
    profile["last_skill_run"]["sprint-planner"] = _now_iso()
    _write_json_atomic(_profile_path(slug), profile)


def _resolve_output_dir(profile: Dict[str, Any], slug: str) -> Path:
    repo = profile.get("repository_path")
    if repo:
        rp = Path(repo)
        if rp.is_dir():
            docs_dir = rp / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            return docs_dir
    fallback = PROFILES_DIR / f"{slug}_docs"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


# --------------------------------------------------------------------------- #
# ID generators                                                               #
# --------------------------------------------------------------------------- #

def _next_sprint_id(sprints: List[Dict]) -> str:
    max_n = 0
    for s in sprints:
        m = re.match(r"^SP(\d+)$", s.get("id", ""))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"SP{max_n + 1:02d}"


def _next_item_id(sidecar: Dict) -> str:
    """Get the next SI## ID, scanning all sprints + backlog for max."""
    max_n = 0
    for s in sidecar.get("sprints", []):
        for item in s.get("items", []):
            m = re.match(r"^SI(\d+)$", item.get("id", ""))
            if m:
                max_n = max(max_n, int(m.group(1)))
    return f"SI{max_n + 1:02d}"


def _next_backlog_id(backlog: List[Dict]) -> str:
    max_n = 0
    for b in backlog:
        m = re.match(r"^BL(\d+)$", b.get("id", ""))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"BL{max_n + 1:02d}"


# --------------------------------------------------------------------------- #
# Sprint helpers                                                              #
# --------------------------------------------------------------------------- #

def _get_active_sprint(sidecar: Dict) -> Optional[Dict]:
    for s in sidecar["sprints"]:
        if s["status"] == "active":
            return s
    return None


def _get_next_planned(sidecar: Dict) -> Optional[Dict]:
    for s in sidecar["sprints"]:
        if s["status"] == "planned":
            return s
    return None


def _compute_effective(hours_per_week: int, sprint_length_weeks: int, buffer_percent: int) -> float:
    raw = hours_per_week * sprint_length_weeks
    return round(raw * (1 - buffer_percent / 100), 1)


def _launch_countdown(sidecar: Dict, profile: Dict) -> Optional[Dict]:
    """Compute launch countdown: remaining sprints vs remaining work."""
    launch_date_str = profile.get("launch_target_date")
    if not launch_date_str:
        return None

    try:
        launch_date = datetime.strptime(launch_date_str, "%Y-%m-%d")
    except ValueError:
        return None

    today = datetime.strptime(_today_str(), "%Y-%m-%d")
    days_remaining = (launch_date - today).days
    if days_remaining < 0:
        return {"status": "overdue", "days_remaining": days_remaining, "message": "Launch date has passed."}

    cap = sidecar["capacity"]
    sprint_days = cap["sprint_length_weeks"] * 7
    sprints_remaining = max(0, days_remaining // sprint_days)
    effective_per_sprint = cap["effective_hours_per_sprint"]

    # Available capacity in remaining sprints.
    available_hours = sprints_remaining * effective_per_sprint

    # Remaining work: backlog + incomplete sprint items.
    backlog_hours = sum(b["estimate_hours"] for b in sidecar["backlog"])
    active = _get_active_sprint(sidecar)
    active_remaining = 0.0
    if active:
        for item in active["items"]:
            if item["status"] in ("todo", "in-progress"):
                active_remaining += item["estimate_hours"]

    total_remaining = backlog_hours + active_remaining

    if available_hours <= 0:
        signal = "red"
    elif total_remaining <= available_hours * 0.8:
        signal = "green"
    elif total_remaining <= available_hours:
        signal = "yellow"
    else:
        signal = "red"

    return {
        "status": signal,
        "days_remaining": days_remaining,
        "sprints_remaining": sprints_remaining,
        "available_hours": available_hours,
        "remaining_work_hours": round(total_remaining, 1),
        "launch_date": launch_date_str,
        "message": {
            "green": f"{sprints_remaining} sprints, {available_hours}h capacity vs {total_remaining}h work -- on track.",
            "yellow": f"{sprints_remaining} sprints, {available_hours}h capacity vs {total_remaining}h work -- tight.",
            "red": f"{sprints_remaining} sprints, {available_hours}h capacity vs {total_remaining}h work -- at risk.",
        }.get(signal, ""),
    }


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_init(args: argparse.Namespace) -> int:
    """Initialize sprint planner with capacity settings and optional backlog."""
    slug = args.slug
    profile = _load_profile(slug)

    if _sprint_path(slug).exists() and not args.force:
        _err(f"Sprint planner already initialized for '{slug}'. Use --force to reset.")
        return 7

    payload = _read_stdin_json()

    # Capacity from payload, falling back to profile values.
    hours_per_week = payload.get("hours_per_week", profile.get("available_hours_per_week", 10))
    sprint_length_weeks = payload.get("sprint_length_weeks", 2)
    buffer_percent = payload.get("buffer_percent", 20)

    if not isinstance(hours_per_week, int) or hours_per_week < 1:
        _err(f"hours_per_week must be a positive integer, got {hours_per_week}.")
        return 6
    if not isinstance(sprint_length_weeks, int) or sprint_length_weeks < 1:
        _err(f"sprint_length_weeks must be a positive integer, got {sprint_length_weeks}.")
        return 6

    effective = _compute_effective(hours_per_week, sprint_length_weeks, buffer_percent)

    now = _now_iso()

    # Build initial backlog from payload if provided.
    backlog = []
    for i, raw_item in enumerate(payload.get("backlog", [])):
        title = raw_item.get("title", "").strip()
        if not title:
            _err(f"Backlog item {i} missing title.")
            return 6
        bl_id = f"BL{i + 1:02d}"
        backlog.append({
            "id": bl_id,
            "title": title,
            "description": raw_item.get("description", ""),
            "estimate_hours": raw_item.get("estimate_hours", 0),
            "priority": raw_item.get("priority", "medium"),
            "category": raw_item.get("category", "feature"),
            "source_id": raw_item.get("source_id", None),
            "added_at": now,
        })

    sidecar = {
        "schema_version": 1,
        "project_slug": slug,
        "created_at": now,
        "updated_at": now,
        "capacity": {
            "hours_per_week": hours_per_week,
            "sprint_length_weeks": sprint_length_weeks,
            "buffer_percent": buffer_percent,
            "effective_hours_per_sprint": effective,
        },
        "sprints": [],
        "backlog": backlog,
        "history": [
            {"at": now, "action": "initialized", "reason": "Sprint planner created"}
        ],
    }

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    total_bl_hours = sum(b["estimate_hours"] for b in backlog)
    print(f"Sprint planner initialized for '{slug}'.")
    print(f"  Capacity    : {hours_per_week}h/week x {sprint_length_weeks}-week sprints = {effective}h effective ({buffer_percent}% buffer)")
    print(f"  Backlog     : {len(backlog)} items, {total_bl_hours}h estimated")

    countdown = _launch_countdown(sidecar, profile)
    if countdown:
        print(f"  Launch      : {countdown['launch_date']} ({countdown['days_remaining']} days) -- {countdown['status'].upper()}")

    return 0


def cmd_add(args: argparse.Namespace) -> int:
    """Add item(s) to the backlog."""
    slug = args.slug
    _load_profile(slug)
    sidecar = _load_sidecar(slug)
    payload = _read_stdin_json()

    items_in = payload.get("items", [])
    if not items_in:
        # Single item mode.
        if "title" in payload:
            items_in = [payload]
        else:
            _err("Payload must include 'items' array or a single item with 'title'.")
            return 6

    now = _now_iso()
    added = []
    for raw in items_in:
        title = raw.get("title", "").strip()
        if not title:
            _err("Each backlog item must have a non-empty 'title'.")
            return 6
        bl_id = _next_backlog_id(sidecar["backlog"])
        item = {
            "id": bl_id,
            "title": title,
            "description": raw.get("description", ""),
            "estimate_hours": raw.get("estimate_hours", 0),
            "priority": raw.get("priority", "medium"),
            "category": raw.get("category", "feature"),
            "source_id": raw.get("source_id", None),
            "added_at": now,
        }
        sidecar["backlog"].append(item)
        added.append(item)

    sidecar["history"].append({
        "at": now,
        "action": "backlog_add",
        "reason": f"Added {len(added)} item(s): {', '.join(a['id'] for a in added)}",
    })

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    for a in added:
        print(f"  Added {a['id']}: {a['title']} ({a['estimate_hours']}h, {a['priority']})")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """Plan the next sprint by pulling items from the backlog."""
    slug = args.slug
    profile = _load_profile(slug)
    sidecar = _load_sidecar(slug)
    payload = _read_stdin_json()

    # Check no active sprint exists (must complete it first).
    active = _get_active_sprint(sidecar)
    if active:
        _err(f"Sprint {active['id']} is still active. Complete it before planning the next one.")
        return 12

    goal = payload.get("goal", "").strip()
    item_ids = payload.get("backlog_ids", [])
    if not item_ids:
        _err("Payload must include 'backlog_ids' -- list of BL## IDs to pull into the sprint.")
        return 6

    # Look up backlog items.
    bl_map = {b["id"]: b for b in sidecar["backlog"]}
    sprint_items = []
    missing = []
    for bid in item_ids:
        if bid in bl_map:
            sprint_items.append(bl_map[bid])
        else:
            missing.append(bid)
    if missing:
        _err(f"Backlog items not found: {', '.join(missing)}")
        return 8

    planned_hours = sum(si["estimate_hours"] for si in sprint_items)
    effective = sidecar["capacity"]["effective_hours_per_sprint"]
    if planned_hours > effective * 1.2:
        _err(f"Planned {planned_hours}h exceeds 120% of sprint capacity ({effective}h). Reduce scope or increase sprint length.")
        return 12

    # Determine dates.
    sprint_weeks = sidecar["capacity"]["sprint_length_weeks"]
    last_sprint = sidecar["sprints"][-1] if sidecar["sprints"] else None
    if last_sprint and last_sprint["status"] == "completed":
        # Start day after last sprint ended.
        try:
            last_end = datetime.strptime(last_sprint["end_date"], "%Y-%m-%d")
            start = last_end + timedelta(days=1)
        except ValueError:
            start = datetime.strptime(_today_str(), "%Y-%m-%d")
    else:
        start = datetime.strptime(_today_str(), "%Y-%m-%d")

    start_str = payload.get("start_date", start.strftime("%Y-%m-%d"))
    try:
        start_dt = datetime.strptime(start_str, "%Y-%m-%d")
    except ValueError:
        _err(f"Invalid start_date format: {start_str}")
        return 6
    end_dt = start_dt + timedelta(weeks=sprint_weeks) - timedelta(days=1)
    end_str = end_dt.strftime("%Y-%m-%d")

    now = _now_iso()
    sprint_id = _next_sprint_id(sidecar["sprints"])

    # Convert backlog items to sprint items.
    converted_items = []
    for bl in sprint_items:
        si_id = _next_item_id(sidecar)
        # Temporarily add to a fake sprint for ID tracking.
        fake = {"items": [{"id": si_id}]}
        sidecar["sprints"].append(fake)  # will be replaced
        converted_items.append({
            "id": si_id,
            "title": bl["title"],
            "description": bl.get("description", ""),
            "estimate_hours": bl["estimate_hours"],
            "actual_hours": None,
            "status": "todo",
            "category": bl.get("category", "feature"),
            "source_id": bl["id"],  # trace back to backlog item
        })
    # Remove the fakes.
    sidecar["sprints"] = [s for s in sidecar["sprints"] if "status" in s]

    sprint = {
        "id": sprint_id,
        "status": "planned",
        "goal": goal,
        "start_date": start_str,
        "end_date": end_str,
        "planned_hours": planned_hours,
        "actual_hours": 0,
        "items": converted_items,
        "retro_notes": "",
        "velocity_hours": None,
    }

    sidecar["sprints"].append(sprint)

    # Remove pulled items from backlog.
    pulled_ids = set(item_ids)
    sidecar["backlog"] = [b for b in sidecar["backlog"] if b["id"] not in pulled_ids]

    sidecar["history"].append({
        "at": now,
        "action": "sprint_planned",
        "reason": f"Planned {sprint_id}: {len(converted_items)} items, {planned_hours}h. {goal}",
    })

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    over_cap = ""
    if planned_hours > effective:
        pct = round((planned_hours / effective - 1) * 100)
        over_cap = f" (WARNING: {pct}% over capacity)"

    print(f"Sprint {sprint_id} planned for '{slug}'.")
    print(f"  Period  : {start_str} to {end_str} ({sprint_weeks} weeks)")
    print(f"  Items   : {len(converted_items)}")
    print(f"  Hours   : {planned_hours}h planned / {effective}h capacity{over_cap}")
    if goal:
        print(f"  Goal    : {goal}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    """Activate the next planned sprint."""
    slug = args.slug
    _load_profile(slug)
    sidecar = _load_sidecar(slug)

    active = _get_active_sprint(sidecar)
    if active:
        _err(f"Sprint {active['id']} is already active. Complete it first.")
        return 12

    planned = _get_next_planned(sidecar)
    if not planned:
        _err("No planned sprint to start. Run 'plan' first.")
        return 10

    planned["status"] = "active"
    now = _now_iso()
    sidecar["history"].append({
        "at": now,
        "action": "sprint_started",
        "reason": f"Started {planned['id']}",
    })

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    print(f"Sprint {planned['id']} is now active.")
    print(f"  Period : {planned['start_date']} to {planned['end_date']}")
    print(f"  Items  : {len(planned['items'])} ({planned['planned_hours']}h planned)")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Update item statuses/hours in the active sprint."""
    slug = args.slug
    _load_profile(slug)
    sidecar = _load_sidecar(slug)
    payload = _read_stdin_json()

    active = _get_active_sprint(sidecar)
    if not active:
        _err("No active sprint. Start one first.")
        return 10

    updates = payload.get("items", [])
    if not updates:
        _err("Payload must include 'items' array with id + status/actual_hours updates.")
        return 6

    item_map = {it["id"]: it for it in active["items"]}
    updated_count = 0
    for upd in updates:
        sid = upd.get("id", "")
        if sid not in item_map:
            _err(f"Item {sid} not found in active sprint {active['id']}.")
            return 8
        item = item_map[sid]
        if "status" in upd:
            item["status"] = upd["status"]
        if "actual_hours" in upd:
            item["actual_hours"] = upd["actual_hours"]
        updated_count += 1

    # Recompute sprint actual_hours.
    active["actual_hours"] = sum(
        it.get("actual_hours") or 0 for it in active["items"]
    )

    now = _now_iso()
    sidecar["history"].append({
        "at": now,
        "action": "sprint_updated",
        "reason": f"Updated {updated_count} item(s) in {active['id']}",
    })

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    done = sum(1 for it in active["items"] if it["status"] == "done")
    total = len(active["items"])
    print(f"Updated {updated_count} item(s) in {active['id']}. Progress: {done}/{total} done.")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    """Complete the active sprint, record velocity, optional retro."""
    slug = args.slug
    profile = _load_profile(slug)
    sidecar = _load_sidecar(slug)

    active = _get_active_sprint(sidecar)
    if not active:
        _err("No active sprint to complete.")
        return 10

    # Compute velocity: sum of actual_hours for done items.
    done_hours = sum(
        (it.get("actual_hours") or it["estimate_hours"])
        for it in active["items"] if it["status"] == "done"
    )

    active["status"] = "completed"
    active["velocity_hours"] = round(done_hours, 1)
    if args.retro:
        active["retro_notes"] = args.retro

    # Move dropped/incomplete items back to backlog.
    returned = []
    remaining_items = []
    for item in active["items"]:
        if item["status"] in ("todo", "in-progress"):
            # Return to backlog.
            bl_id = _next_backlog_id(sidecar["backlog"])
            sidecar["backlog"].append({
                "id": bl_id,
                "title": item["title"],
                "description": item.get("description", ""),
                "estimate_hours": item["estimate_hours"],
                "priority": "high",  # bumped -- it was committed.
                "category": item.get("category", "feature"),
                "source_id": item["id"],
                "added_at": _now_iso(),
            })
            returned.append(item["id"])
            remaining_items.append(item)
        else:
            remaining_items.append(item)

    now = _now_iso()
    reason = f"Completed {active['id']}: velocity={done_hours}h"
    if returned:
        reason += f", returned {len(returned)} item(s) to backlog"
    sidecar["history"].append({"at": now, "action": "sprint_completed", "reason": reason})

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    done_count = sum(1 for it in active["items"] if it["status"] == "done")
    dropped_count = sum(1 for it in active["items"] if it["status"] == "dropped")
    print(f"Sprint {active['id']} completed.")
    print(f"  Done     : {done_count} items")
    print(f"  Dropped  : {dropped_count} items")
    if returned:
        print(f"  Returned : {len(returned)} incomplete item(s) to backlog (priority bumped to high)")
    print(f"  Velocity : {done_hours}h")

    countdown = _launch_countdown(sidecar, profile)
    if countdown:
        print(f"  Launch   : {countdown['status'].upper()} -- {countdown['message']}")

    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Display current sprint planner state."""
    slug = args.slug
    profile = _load_profile(slug)
    sidecar = _load_sidecar(slug)

    if args.json:
        print(json.dumps(sidecar, indent=2))
        return 0

    cap = sidecar["capacity"]
    print(f"{profile.get('project_name', slug)}  ({slug}) -- Sprint Planner")
    print(f"  {'=' * 50}")

    # Capacity.
    print(f"\n  Capacity: {cap['hours_per_week']}h/week x {cap['sprint_length_weeks']}-week sprints = {cap['effective_hours_per_sprint']}h effective ({cap['buffer_percent']}% buffer)")

    # Velocity.
    completed = [s for s in sidecar["sprints"] if s["status"] == "completed"]
    if completed:
        velocities = [s["velocity_hours"] for s in completed if s.get("velocity_hours") is not None]
        if velocities:
            avg = round(sum(velocities) / len(velocities), 1)
            print(f"  Velocity: {avg}h avg over {len(velocities)} sprint(s)")
    else:
        print("  Velocity: no completed sprints yet")

    # Launch countdown.
    countdown = _launch_countdown(sidecar, profile)
    if countdown:
        print(f"  Launch  : {countdown['launch_date']} ({countdown['days_remaining']} days) -- {countdown['status'].upper()}")
        print(f"            {countdown['message']}")

    # Active sprint.
    active = _get_active_sprint(sidecar)
    if active:
        done = sum(1 for it in active["items"] if it["status"] == "done")
        total = len(active["items"])
        print(f"\n  Active: {active['id']} ({active['start_date']} to {active['end_date']})")
        if active.get("goal"):
            print(f"    Goal: {active['goal']}")
        print(f"    Progress: {done}/{total} items done, {active['actual_hours']}/{active['planned_hours']}h logged")
        for item in active["items"]:
            status_mark = {"todo": "[ ]", "in-progress": "[~]", "done": "[x]", "dropped": "[-]"}.get(item["status"], "[ ]")
            hrs = f" ({item.get('actual_hours') or item['estimate_hours']}h)" if item["estimate_hours"] else ""
            print(f"    {status_mark} {item['id']}  {item['title']}{hrs}")
    else:
        print("\n  No active sprint.")

    # Planned sprints.
    planned = [s for s in sidecar["sprints"] if s["status"] == "planned"]
    if planned:
        print(f"\n  Planned: {len(planned)} sprint(s)")
        for sp in planned:
            print(f"    {sp['id']}: {sp['start_date']} to {sp['end_date']} ({sp['planned_hours']}h, {len(sp['items'])} items)")

    # Backlog.
    if sidecar["backlog"]:
        total_bl = sum(b["estimate_hours"] for b in sidecar["backlog"])
        print(f"\n  Backlog: {len(sidecar['backlog'])} items, {total_bl}h estimated")
        # Sort by priority for display.
        prio_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_bl = sorted(sidecar["backlog"], key=lambda b: prio_order.get(b["priority"], 9))
        for b in sorted_bl:
            print(f"    {b['id']}  [{b['priority'][:4]}]  {b['title']} ({b['estimate_hours']}h)")
    else:
        print("\n  Backlog: empty")

    return 0


def cmd_render(args: argparse.Namespace) -> int:
    """Generate SPRINT_PLAN.md from sidecar."""
    slug = args.slug
    profile = _load_profile(slug)
    sidecar = _load_sidecar(slug)

    if not SPRINT_MD_TMPL.exists():
        _err(f"Template not found at {SPRINT_MD_TMPL}")
        sys.exit(2)

    template = SPRINT_MD_TMPL.read_text(encoding="utf-8")

    cap = sidecar["capacity"]
    project_name = profile.get("project_name", slug)

    # Capacity block.
    capacity_block = (
        f"| Setting | Value |\n"
        f"|---------|-------|\n"
        f"| Hours per week | {cap['hours_per_week']} |\n"
        f"| Sprint length | {cap['sprint_length_weeks']} weeks |\n"
        f"| Buffer | {cap['buffer_percent']}% |\n"
        f"| Effective hours/sprint | {cap['effective_hours_per_sprint']} |"
    )

    # Velocity block.
    completed = [s for s in sidecar["sprints"] if s["status"] == "completed"]
    velocities = [s["velocity_hours"] for s in completed if s.get("velocity_hours") is not None]
    if velocities:
        avg = round(sum(velocities) / len(velocities), 1)
        vel_rows = [f"| Sprint | Velocity |", f"|--------|----------|"]
        for s in completed:
            v = s.get("velocity_hours", "?")
            vel_rows.append(f"| {s['id']} | {v}h |")
        vel_rows.append(f"| **Average** | **{avg}h** |")
        velocity_block = "\n".join(vel_rows)
    else:
        velocity_block = "_No completed sprints yet. Velocity data will appear after the first sprint._"

    # Launch countdown block.
    countdown = _launch_countdown(sidecar, profile)
    if countdown:
        signal_display = {"green": "ON TRACK", "yellow": "TIGHT", "red": "AT RISK", "overdue": "OVERDUE"}
        countdown_block = (
            f"**Target:** {countdown['launch_date']} ({countdown['days_remaining']} days)\n\n"
            f"**Signal:** {signal_display.get(countdown['status'], countdown['status'])}\n\n"
            f"{countdown['message']}"
        )
    else:
        countdown_block = "_No launch_target_date set in profile._"

    # Active sprint block.
    active = _get_active_sprint(sidecar)
    if active:
        done = sum(1 for it in active["items"] if it["status"] == "done")
        total = len(active["items"])
        rows = [f"**{active['id']}** | {active['start_date']} to {active['end_date']} | {done}/{total} done | {active['actual_hours']}/{active['planned_hours']}h\n"]
        if active.get("goal"):
            rows.append(f"**Goal:** {active['goal']}\n")
        rows.append(f"| Item | Title | Est | Actual | Status |")
        rows.append(f"|------|-------|-----|--------|--------|")
        for item in active["items"]:
            actual = item.get("actual_hours")
            actual_str = f"{actual}h" if actual is not None else "-"
            title_safe = item["title"].replace("|", "/")
            rows.append(f"| {item['id']} | {title_safe} | {item['estimate_hours']}h | {actual_str} | {item['status']} |")
        active_sprint_block = "\n".join(rows)
    else:
        active_sprint_block = "_No active sprint._"

    # Upcoming block.
    planned = [s for s in sidecar["sprints"] if s["status"] == "planned"]
    if planned:
        rows = ["| Sprint | Period | Items | Hours |", "|--------|--------|-------|-------|"]
        for sp in planned:
            rows.append(f"| {sp['id']} | {sp['start_date']} to {sp['end_date']} | {len(sp['items'])} | {sp['planned_hours']}h |")
        upcoming_block = "\n".join(rows)
    else:
        upcoming_block = "_No planned sprints._"

    # Completed block.
    if completed:
        rows = ["| Sprint | Period | Velocity | Done | Dropped |", "|--------|--------|----------|------|---------|"]
        for sp in completed:
            done_c = sum(1 for it in sp["items"] if it["status"] == "done")
            dropped_c = sum(1 for it in sp["items"] if it["status"] == "dropped")
            v = sp.get("velocity_hours", "?")
            rows.append(f"| {sp['id']} | {sp['start_date']} to {sp['end_date']} | {v}h | {done_c} | {dropped_c} |")
            if sp.get("retro_notes"):
                retro_safe = sp["retro_notes"].replace("|", "/").replace("\n", " ")
                rows.append(f"| | _Retro: {retro_safe}_ | | | |")
        completed_block = "\n".join(rows)
    else:
        completed_block = "_No completed sprints yet._"

    # Backlog block.
    if sidecar["backlog"]:
        prio_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_bl = sorted(sidecar["backlog"], key=lambda b: prio_order.get(b["priority"], 9))
        rows = ["| ID | Priority | Title | Est | Category |", "|----|----------|-------|-----|----------|"]
        for b in sorted_bl:
            title_safe = b["title"].replace("|", "/")
            cat = b.get("category", "")
            rows.append(f"| {b['id']} | {b['priority']} | {title_safe} | {b['estimate_hours']}h | {cat} |")
        total_bl = sum(b["estimate_hours"] for b in sidecar["backlog"])
        rows.append(f"\n**Total:** {len(sidecar['backlog'])} items, {total_bl}h estimated")
        backlog_block = "\n".join(rows)
    else:
        backlog_block = "_Backlog is empty._"

    # History block.
    if sidecar["history"]:
        rows = ["| When | Action | Detail |", "|------|--------|--------|"]
        for h in reversed(sidecar["history"][-20:]):
            at_short = h["at"][:10]
            action_safe = h["action"].replace("|", "/")
            reason_safe = h["reason"].replace("|", "/")
            rows.append(f"| {at_short} | {action_safe} | {reason_safe} |")
        history_block = "\n".join(rows)
    else:
        history_block = "_No history yet._"

    # Render.
    md = template
    md = md.replace("{{project_name}}", project_name)
    md = md.replace("{{project_slug}}", slug)
    md = md.replace("{{capacity_block}}", capacity_block)
    md = md.replace("{{velocity_block}}", velocity_block)
    md = md.replace("{{countdown_block}}", countdown_block)
    md = md.replace("{{active_sprint_block}}", active_sprint_block)
    md = md.replace("{{upcoming_block}}", upcoming_block)
    md = md.replace("{{completed_block}}", completed_block)
    md = md.replace("{{backlog_block}}", backlog_block)
    md = md.replace("{{history_block}}", history_block)

    output_dir = _resolve_output_dir(profile, slug)
    out_path = output_dir / "SPRINT_PLAN.md"
    out_path.write_text(md, encoding="utf-8")

    print(f"Rendered: {out_path}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Remove sprint sidecar."""
    slug = args.slug
    if not _sprint_path(slug).exists():
        _err(f"No sprint sidecar found for '{slug}'.")
        return 10

    if not args.yes:
        _err("Pass --yes to confirm deletion.")
        return 9

    _sprint_path(slug).unlink()
    print(f"Sprint planner sidecar deleted for '{slug}'.")
    return 0


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(prog="sprint_tool.py", description="Solo-dev sprint planner")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Initialize sprint planner")
    p_init.add_argument("slug")
    p_init.add_argument("--from-stdin", action="store_true")
    p_init.add_argument("--force", action="store_true")

    p_add = sub.add_parser("add", help="Add item(s) to backlog")
    p_add.add_argument("slug")
    p_add.add_argument("--from-stdin", action="store_true")

    p_plan = sub.add_parser("plan", help="Plan next sprint from backlog")
    p_plan.add_argument("slug")
    p_plan.add_argument("--from-stdin", action="store_true")

    p_start = sub.add_parser("start", help="Activate next planned sprint")
    p_start.add_argument("slug")

    p_update = sub.add_parser("update", help="Update item statuses in active sprint")
    p_update.add_argument("slug")
    p_update.add_argument("--from-stdin", action="store_true")

    p_complete = sub.add_parser("complete", help="Complete the active sprint")
    p_complete.add_argument("slug")
    p_complete.add_argument("--retro", type=str, default="", help="Retrospective notes")

    p_show = sub.add_parser("show", help="Display current state")
    p_show.add_argument("slug")
    p_show.add_argument("--json", action="store_true")

    p_render = sub.add_parser("render", help="Generate SPRINT_PLAN.md")
    p_render.add_argument("slug")

    p_delete = sub.add_parser("delete", help="Remove sprint sidecar")
    p_delete.add_argument("slug")
    p_delete.add_argument("--yes", action="store_true")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    dispatch = {
        "init": cmd_init,
        "add": cmd_add,
        "plan": cmd_plan,
        "start": cmd_start,
        "update": cmd_update,
        "complete": cmd_complete,
        "show": cmd_show,
        "render": cmd_render,
        "delete": cmd_delete,
    }

    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
