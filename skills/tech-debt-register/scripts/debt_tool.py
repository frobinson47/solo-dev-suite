#!/usr/bin/env python3
"""
debt_tool.py -- The workhorse for the tech-debt-register skill.

Maintains an append-only log of tech debt with categorization, impact scoring,
and pay-down window recommendations. Turns "I know there's a mess in there"
into a managed backlog.

Commands:
    log      <slug> --from-stdin                        # Add a new debt item
    list     <slug> [--status s] [--category c] [--recommend] [--json]
    show     <slug> --id <ID>
    resolve  <slug> --id <ID> --resolution-notes "..."
    accept   <slug> --id <ID> --reason "..."
    reopen   <slug> --id <ID>
    render   <slug> [--output-dir <dir>]
    delete   <slug> [--yes]
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


# --------------------------------------------------------------------------- #
# Paths                                                                       #
# --------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
SCHEMA_PATH = TEMPLATES_DIR / "techdebt.schema.json"
RENDER_TMPL = TEMPLATES_DIR / "TECH_DEBT.md.tmpl"


def _find_suite_dir() -> Path:
    import os
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
    print(f"[debt_tool] {msg}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _human_date(iso: Optional[str]) -> str:
    if not iso:
        return "(not set)"
    try:
        dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%B %d, %Y at %H:%M UTC")
    except ValueError:
        return iso


def _profile_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.json"


def _debt_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.techdebt.json"


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


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
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
        if schema.get("uniqueItems") and len(value) != len({json.dumps(v, sort_keys=True) for v in value}):
            errors.append(f"{path}: items are not unique")
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
# Priority scoring                                                            #
# --------------------------------------------------------------------------- #

_IMPACT_RANK = {"low": 1, "medium": 2, "high": 4, "critical": 8}
_URGENCY_RANK = {
    "never": 0, "when-it-bites": 1, "post-launch-90d": 2,
    "post-launch-30d": 3, "pre-launch": 4, "now": 5,
}
_EFFORT_RANK = {"S": 1, "M": 2, "L": 3, "XL": 4}


def _priority_score(item: Dict[str, Any]) -> float:
    impact = _IMPACT_RANK.get(item["impact"], 2)
    urgency = _URGENCY_RANK.get(item["urgency_window"], 1)
    effort = _EFFORT_RANK.get(item["effort"], 2)
    if effort == 0:
        effort = 1
    return (impact * urgency) / effort


# --------------------------------------------------------------------------- #
# Sidecar helpers                                                             #
# --------------------------------------------------------------------------- #

def _load_or_create_sidecar(slug: str) -> Dict[str, Any]:
    """Load existing sidecar or create a fresh one on first log."""
    data = _read_json(_debt_path(slug))
    if data is not None:
        return data
    now = _now_iso()
    return {
        "schema_version": 1,
        "project_slug": slug,
        "created_at": now,
        "updated_at": now,
        "items": [],
        "change_log": [],
    }


def _load_sidecar(slug: str) -> Dict[str, Any]:
    data = _read_json(_debt_path(slug))
    if data is None:
        _err(f"No tech debt sidecar for '{slug}'. Log an item first.")
        sys.exit(10)
    return data


def _load_profile(slug: str) -> Dict[str, Any]:
    data = _read_json(_profile_path(slug))
    if data is None:
        _err(f"No profile for '{slug}'. Onboard the project first.")
        sys.exit(2)
    return data


def _save_sidecar(slug: str, data: Dict[str, Any]) -> None:
    data["updated_at"] = _now_iso()
    errors = _validate_sidecar(data)
    if errors:
        _err(f"Sidecar validation failed:\n  " + "\n  ".join(errors))
        sys.exit(4)
    _write_json_atomic(_debt_path(slug), data)


def _next_id(items: List[Dict[str, Any]]) -> str:
    """Monotonic TD01, TD02, ... IDs. Never recycled."""
    max_n = 0
    for item in items:
        m = re.match(r'^TD(\d+)$', item.get("id", ""))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"TD{max_n + 1:02d}"


def _find_item(items: List[Dict[str, Any]], item_id: str) -> Optional[Dict[str, Any]]:
    for item in items:
        if item["id"] == item_id:
            return item
    return None


# --------------------------------------------------------------------------- #
# Output directory resolution                                                 #
# --------------------------------------------------------------------------- #

def _resolve_output_dir(profile: Dict[str, Any], slug: str) -> Path:
    repo = profile.get("repository_path")
    if repo:
        repo_path = Path(repo)
        if repo_path.is_dir():
            return repo_path / "docs"
    return PROFILES_DIR / f"{slug}_docs"


# --------------------------------------------------------------------------- #
# Profile mirror                                                              #
# --------------------------------------------------------------------------- #

def _mirror_to_profile(slug: str, sidecar: Dict[str, Any]) -> None:
    profile = _load_profile(slug)

    open_items = [i for i in sidecar["items"] if i["status"] == "open"]
    by_cat: Dict[str, int] = {}
    for item in open_items:
        for cat in item["categories"]:
            by_cat[cat] = by_cat.get(cat, 0) + 1

    high_open = sum(1 for i in open_items if i["impact"] == "high")
    critical_open = sum(1 for i in open_items if i["impact"] == "critical")

    profile["techdebt_model"] = {
        "total_open": len(open_items),
        "by_category": by_cat,
        "high_impact_open": high_open,
        "critical_open": critical_open,
        "last_logged": sidecar["updated_at"],
    }

    if "last_skill_run" not in profile:
        profile["last_skill_run"] = {}
    profile["last_skill_run"]["tech-debt-register"] = _now_iso()
    profile["updated_at"] = _now_iso()
    _write_json_atomic(_profile_path(slug), profile)


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_log(args: argparse.Namespace) -> None:
    slug = args.slug
    _ = _load_profile(slug)  # verify profile exists
    sidecar = _load_or_create_sidecar(slug)

    payload = _read_stdin_json()

    if "title" not in payload or not payload["title"]:
        _err("Missing required field: title")
        sys.exit(6)
    if "description" not in payload:
        _err("Missing required field: description")
        sys.exit(6)

    # Validate categories
    valid_cats = ["design", "code", "infra", "docs", "dependencies",
                  "security", "ui-ux", "testing", "performance"]
    cats = payload.get("categories", ["code"])
    if not isinstance(cats, list) or not cats:
        _err("categories must be a non-empty array")
        sys.exit(6)
    bad = [c for c in cats if c not in valid_cats]
    if bad:
        _err(f"Invalid categories: {', '.join(bad)}. Valid: {', '.join(valid_cats)}")
        sys.exit(6)

    # Validate enums
    valid_impact = ["low", "medium", "high", "critical"]
    impact = payload.get("impact", "medium")
    if impact not in valid_impact:
        _err(f"impact must be one of: {', '.join(valid_impact)}")
        sys.exit(6)

    valid_effort = ["S", "M", "L", "XL"]
    effort = payload.get("effort", "M")
    if effort not in valid_effort:
        _err(f"effort must be one of: {', '.join(valid_effort)}")
        sys.exit(6)

    valid_urgency = ["now", "pre-launch", "post-launch-30d", "post-launch-90d", "when-it-bites", "never"]
    urgency = payload.get("urgency_window", "when-it-bites")
    if urgency not in valid_urgency:
        _err(f"urgency_window must be one of: {', '.join(valid_urgency)}")
        sys.exit(6)

    now = _now_iso()
    item_id = _next_id(sidecar["items"])

    item = {
        "id": item_id,
        "title": payload["title"],
        "description": payload.get("description", ""),
        "categories": cats,
        "status": "open",
        "impact": impact,
        "effort": effort,
        "urgency_window": urgency,
        "added_at": now,
        "resolved_at": None,
        "resolution_notes": "",
        "estimated_hours": payload.get("estimated_hours", None),
        "related_adrs": payload.get("related_adrs", []),
        "notes": payload.get("notes", ""),
    }

    sidecar["items"].append(item)
    sidecar["change_log"].append({
        "at": now,
        "item_id": item_id,
        "action": "added",
        "notes": item["title"],
    })

    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    score = _priority_score(item)
    print(f"Logged {item_id}: {item['title']}")
    print(f"  Impact: {impact} | Effort: {effort} | Urgency: {urgency}")
    print(f"  Priority score: {score:.1f}")
    print(f"  Categories: {', '.join(cats)}")


def cmd_list(args: argparse.Namespace) -> None:
    slug = args.slug
    sidecar = _load_sidecar(slug)
    items = sidecar["items"]

    # Filter by status
    status_filter = getattr(args, 'status', None)
    if status_filter:
        items = [i for i in items if i["status"] == status_filter]
    else:
        # Default: show open items only
        items = [i for i in items if i["status"] == "open"]

    # Filter by category
    cat_filter = getattr(args, 'category', None)
    if cat_filter:
        items = [i for i in items if cat_filter in i["categories"]]

    # Sort by recommendation
    recommend = getattr(args, 'recommend', False)
    if recommend:
        items.sort(key=lambda i: _priority_score(i), reverse=True)

    if getattr(args, 'json', False):
        print(json.dumps(items, indent=2))
        return

    if not items:
        print(f"No items found for '{slug}' with current filters.")
        return

    print(f"=== Tech Debt: {slug} ({len(items)} items) ===")
    if recommend:
        print("(sorted by pay-down priority)")
    print()

    for item in items:
        score = _priority_score(item)
        cats = ", ".join(item["categories"])
        print(f"  {item['id']}  [{item['impact'].upper()}] [{item['effort']}] [{item['urgency_window']}]  score={score:.1f}")
        print(f"         {item['title']}")
        print(f"         Categories: {cats}")
        print()


def cmd_show(args: argparse.Namespace) -> None:
    slug = args.slug
    sidecar = _load_sidecar(slug)
    item_id = args.id

    item = _find_item(sidecar["items"], item_id)
    if not item:
        _err(f"No item with ID '{item_id}' in '{slug}'.")
        sys.exit(8)

    score = _priority_score(item)
    print(f"=== {item['id']}: {item['title']} ===")
    print(f"Status:        {item['status']}")
    print(f"Impact:        {item['impact']}")
    print(f"Effort:        {item['effort']}")
    print(f"Urgency:       {item['urgency_window']}")
    print(f"Priority:      {score:.1f}")
    print(f"Categories:    {', '.join(item['categories'])}")
    print(f"Added:         {_human_date(item['added_at'])}")
    if item["resolved_at"]:
        print(f"Resolved:      {_human_date(item['resolved_at'])}")
    if item["resolution_notes"]:
        print(f"Resolution:    {item['resolution_notes']}")
    if item["estimated_hours"] is not None:
        print(f"Est. hours:    {item['estimated_hours']}")
    if item["related_adrs"]:
        print(f"Related ADRs:  {', '.join(str(a) for a in item['related_adrs'])}")
    if item["description"]:
        print(f"Description:   {item['description']}")
    if item["notes"]:
        print(f"Notes:         {item['notes']}")


def cmd_resolve(args: argparse.Namespace) -> None:
    slug = args.slug
    sidecar = _load_sidecar(slug)
    item_id = args.id

    item = _find_item(sidecar["items"], item_id)
    if not item:
        _err(f"No item with ID '{item_id}'.")
        sys.exit(8)

    if item["status"] == "paid-down":
        _err(f"{item_id} is already resolved.")
        sys.exit(12)

    resolution = getattr(args, 'resolution_notes', '') or ''
    if not resolution:
        _err("--resolution-notes is required when resolving.")
        sys.exit(11)

    now = _now_iso()
    item["status"] = "paid-down"
    item["resolved_at"] = now
    item["resolution_notes"] = resolution

    sidecar["change_log"].append({
        "at": now,
        "item_id": item_id,
        "action": "resolved",
        "notes": resolution,
    })

    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    print(f"Resolved {item_id}: {item['title']}")
    print(f"  Resolution: {resolution}")


def cmd_accept(args: argparse.Namespace) -> None:
    slug = args.slug
    sidecar = _load_sidecar(slug)
    item_id = args.id

    item = _find_item(sidecar["items"], item_id)
    if not item:
        _err(f"No item with ID '{item_id}'.")
        sys.exit(8)

    if item["status"] == "accepted":
        _err(f"{item_id} is already accepted.")
        sys.exit(12)

    reason = getattr(args, 'reason', '') or ''
    if not reason:
        _err("--reason is required when accepting debt.")
        sys.exit(11)

    now = _now_iso()
    item["status"] = "accepted"
    item["resolution_notes"] = f"Accepted: {reason}"

    sidecar["change_log"].append({
        "at": now,
        "item_id": item_id,
        "action": "accepted",
        "notes": reason,
    })

    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    print(f"Accepted {item_id}: {item['title']}")
    print(f"  Reason: {reason}")


def cmd_reopen(args: argparse.Namespace) -> None:
    slug = args.slug
    sidecar = _load_sidecar(slug)
    item_id = args.id

    item = _find_item(sidecar["items"], item_id)
    if not item:
        _err(f"No item with ID '{item_id}'.")
        sys.exit(8)

    if item["status"] == "open":
        _err(f"{item_id} is already open.")
        sys.exit(12)

    now = _now_iso()
    item["status"] = "open"
    item["resolved_at"] = None

    sidecar["change_log"].append({
        "at": now,
        "item_id": item_id,
        "action": "reopened",
        "notes": "Reopened",
    })

    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    print(f"Reopened {item_id}: {item['title']}")


def cmd_render(args: argparse.Namespace) -> None:
    slug = args.slug
    profile = _load_profile(slug)
    sidecar = _load_sidecar(slug)

    output_dir = Path(args.output_dir) if getattr(args, 'output_dir', None) else _resolve_output_dir(profile, slug)

    items = sidecar["items"]
    open_items = [i for i in items if i["status"] == "open"]
    resolved_items = [i for i in items if i["status"] == "paid-down"]
    accepted_items = [i for i in items if i["status"] == "accepted"]

    critical_open = sum(1 for i in open_items if i["impact"] == "critical")
    high_open = sum(1 for i in open_items if i["impact"] == "high")

    # Recommend block: top 5 open by priority score
    recommended = sorted(open_items, key=_priority_score, reverse=True)[:5]
    if recommended:
        rec_lines = ["| Rank | ID | Title | Impact | Effort | Urgency | Score |",
                      "|------|----|-------|--------|--------|---------|-------|"]
        for rank, item in enumerate(recommended, 1):
            score = _priority_score(item)
            title = item['title'].replace('|', '\\|')
            rec_lines.append(
                f"| {rank} | {item['id']} | {title} | {item['impact']} | {item['effort']} | {item['urgency_window']} | {score:.1f} |"
            )
        recommend_block = "\n".join(rec_lines)
    else:
        recommend_block = "_No open items to recommend._"

    # Open block: grouped by category
    if open_items:
        cats_seen: Dict[str, List[Dict[str, Any]]] = {}
        for item in open_items:
            for cat in item["categories"]:
                cats_seen.setdefault(cat, []).append(item)
        open_lines = []
        for cat in sorted(cats_seen.keys()):
            open_lines.append(f"### {cat}")
            open_lines.append("")
            open_lines.append("| ID | Title | Impact | Effort | Urgency |")
            open_lines.append("|----|-------|--------|--------|---------|")
            for item in cats_seen[cat]:
                title = item['title'].replace('|', '\\|')
                open_lines.append(f"| {item['id']} | {title} | {item['impact']} | {item['effort']} | {item['urgency_window']} |")
            open_lines.append("")
        open_block = "\n".join(open_lines)
    else:
        open_block = "_No open tech debt. Nice._"

    # Resolved block
    if resolved_items:
        res_lines = ["| ID | Title | Resolution |",
                     "|----|-------|------------|"]
        for item in resolved_items:
            title = item['title'].replace('|', '\\|')
            notes = item['resolution_notes'].replace('|', '\\|')
            res_lines.append(f"| {item['id']} | {title} | {notes} |")
        resolved_block = "\n".join(res_lines)
    else:
        resolved_block = "_Nothing resolved yet._"

    # Accepted block
    if accepted_items:
        acc_lines = ["| ID | Title | Rationale |",
                     "|----|-------|-----------|"]
        for item in accepted_items:
            title = item['title'].replace('|', '\\|')
            notes = item['resolution_notes'].replace('|', '\\|')
            acc_lines.append(f"| {item['id']} | {title} | {notes} |")
        accepted_block = "\n".join(acc_lines)
    else:
        accepted_block = "_No accepted debt._"

    # Change log (last 20)
    cl = sidecar["change_log"][-20:]
    if cl:
        cl_lines = ["| Date | Item | Action | Notes |",
                     "|------|------|--------|-------|"]
        for entry in reversed(cl):
            date = _human_date(entry["at"])
            notes = entry['notes'].replace('|', '\\|')
            cl_lines.append(f"| {date} | {entry['item_id']} | {entry['action']} | {notes} |")
        changelog_block = "\n".join(cl_lines)
    else:
        changelog_block = "_No history yet._"

    # Render template
    tmpl = RENDER_TMPL.read_text(encoding="utf-8")
    project_name = profile.get("project_name", slug)

    result = tmpl
    result = result.replace("{{project_name}}", project_name.replace('|', '\\|'))
    result = result.replace("{{project_slug}}", slug)
    result = result.replace("{{updated_at_human}}", _human_date(sidecar["updated_at"]))
    result = result.replace("{{total_items}}", str(len(items)))
    result = result.replace("{{open_count}}", str(len(open_items)))
    result = result.replace("{{paid_down_count}}", str(len(resolved_items)))
    result = result.replace("{{accepted_count}}", str(len(accepted_items)))
    result = result.replace("{{critical_open}}", str(critical_open))
    result = result.replace("{{high_impact_open}}", str(high_open))
    result = result.replace("{{recommend_block}}", recommend_block)
    result = result.replace("{{open_block}}", open_block)
    result = result.replace("{{resolved_block}}", resolved_block)
    result = result.replace("{{accepted_block}}", accepted_block)
    result = result.replace("{{changelog_block}}", changelog_block)

    out_path = output_dir / "TECH_DEBT.md"
    _write_text_atomic(out_path, result)
    print(f"Rendered: {out_path}")


def cmd_delete(args: argparse.Namespace) -> None:
    slug = args.slug
    path = _debt_path(slug)

    if not path.exists():
        _err(f"No tech debt sidecar for '{slug}'.")
        sys.exit(10)

    if not getattr(args, 'yes', False):
        _err(f"This will delete the tech debt register for '{slug}'. Pass --yes to confirm.")
        sys.exit(9)

    path.unlink()
    print(f"Tech debt sidecar deleted for '{slug}'.")


# --------------------------------------------------------------------------- #
# CLI wiring                                                                  #
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="debt_tool.py",
        description="Tech Debt Register: log, track, and prioritize tech debt."
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    # log
    p_log = sub.add_parser("log", help="Log a new debt item from stdin")
    p_log.add_argument("slug")
    p_log.add_argument("--from-stdin", action="store_true", default=True)

    # list
    p_list = sub.add_parser("list", help="List debt items")
    p_list.add_argument("slug")
    p_list.add_argument("--status", choices=["open", "paid-down", "accepted"])
    p_list.add_argument("--category")
    p_list.add_argument("--recommend", action="store_true")
    p_list.add_argument("--json", action="store_true")

    # show
    p_show = sub.add_parser("show", help="Show a single item")
    p_show.add_argument("slug")
    p_show.add_argument("--id", required=True)

    # resolve
    p_res = sub.add_parser("resolve", help="Mark an item as paid-down")
    p_res.add_argument("slug")
    p_res.add_argument("--id", required=True)
    p_res.add_argument("--resolution-notes", required=True)

    # accept
    p_acc = sub.add_parser("accept", help="Accept debt as won't-fix")
    p_acc.add_argument("slug")
    p_acc.add_argument("--id", required=True)
    p_acc.add_argument("--reason", required=True)

    # reopen
    p_reopen = sub.add_parser("reopen", help="Reopen a resolved/accepted item")
    p_reopen.add_argument("slug")
    p_reopen.add_argument("--id", required=True)

    # render
    p_render = sub.add_parser("render", help="Generate TECH_DEBT.md")
    p_render.add_argument("slug")
    p_render.add_argument("--output-dir")

    # delete
    p_del = sub.add_parser("delete", help="Delete the sidecar")
    p_del.add_argument("slug")
    p_del.add_argument("--yes", action="store_true")

    args = parser.parse_args()

    commands = {
        "log": cmd_log,
        "list": cmd_list,
        "show": cmd_show,
        "resolve": cmd_resolve,
        "accept": cmd_accept,
        "reopen": cmd_reopen,
        "render": cmd_render,
        "delete": cmd_delete,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
