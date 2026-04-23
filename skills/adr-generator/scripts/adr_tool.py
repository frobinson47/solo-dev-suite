#!/usr/bin/env python3
"""
adr_tool.py -- Architecture Decision Record generator for the adr-generator skill.

Owns:
  * The per-project sidecar at solo-dev-suite/profiles/<slug>.adr.json
  * The profile mirror at profile.adr_model (updated on every write)
  * The ADR Markdown files at <repo>/docs/adr/NNNN-<slug>.md
  * The index file at <repo>/docs/adr/index.md

Commands:
    new        <slug> --from-stdin                          # Create new ADR
    show       <slug> --number <N> [--json]                 # View single ADR
    list       <slug> [--status <s>] [--tag <t>] [--json]   # List all ADRs
    supersede  <slug> --old-number <N> --new-number <M>     # Mark old as superseded by new
    status     <slug> --number <N> --to <status>            # Change ADR status
    render     <slug> [--output-dir <path>]                 # Re-render all ADR .md files + index
    delete     <slug> [--yes]                               # Remove sidecar (keeps .md files)

Design notes:
  * The sidecar stores full ADR content (context, decision, consequences, alternatives)
    so we can re-render .md files from the sidecar at any time.
  * ADR Markdown files are the human-facing output; sidecar is the machine-facing source.
  * Numbers are sequential, never recycled, zero-padded to 4 digits.
  * Supersession is bidirectional: old gets superseded_by, new gets supersedes.
  * Status transitions are validated: proposed->accepted, accepted->deprecated|superseded.
  * 'delete' removes the sidecar but NOT the .md files -- those are repo history.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- #
# Path discovery                                                              #
# --------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
SCHEMA_PATH = TEMPLATES_DIR / "adr.schema.json"


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
    print(f"[adr_tool] {msg}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _human_date(iso: Optional[str]) -> str:
    if not iso:
        return "(not set)"
    try:
        dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return iso


def _profile_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.json"


def _sidecar_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.adr.json"


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
    """Write a text file atomically (for .md files)."""
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
# JSON Schema validation (inline -- same minimal validator as scope_tool.py)  #
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
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: {len(value)} items > maxItems {schema['maxItems']}")
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
# Profile helpers                                                             #
# --------------------------------------------------------------------------- #

def _load_profile(slug: str) -> Dict[str, Any]:
    pp = _profile_path(slug)
    if not pp.exists():
        _err(f"Profile not found: {pp}")
        sys.exit(2)
    data = _read_json(pp)
    if data is None:
        _err(f"Cannot read profile: {pp}")
        sys.exit(3)
    return data


def _mirror_to_profile(slug: str, sidecar: Dict[str, Any]) -> None:
    """Write lean ADR summary to profile.adr_model + update last_skill_run."""
    profile = _load_profile(slug)
    adrs = sidecar.get("adrs", [])

    # Count by status
    counts: Dict[str, int] = {}
    for a in adrs:
        s = a["status"]
        counts[s] = counts.get(s, 0) + 1

    latest_num = max((a["number"] for a in adrs), default=0)
    latest_title = ""
    for a in adrs:
        if a["number"] == latest_num:
            latest_title = a["title"]

    profile["adr_model"] = {
        "total_adrs": len(adrs),
        "accepted": counts.get("accepted", 0),
        "proposed": counts.get("proposed", 0),
        "superseded": counts.get("superseded", 0),
        "deprecated": counts.get("deprecated", 0),
        "latest_number": latest_num,
        "latest_title": latest_title,
    }

    if "last_skill_run" not in profile:
        profile["last_skill_run"] = {}
    profile["last_skill_run"]["adr-generator"] = _now_iso()

    _write_json_atomic(_profile_path(slug), profile)


# --------------------------------------------------------------------------- #
# Sidecar I/O                                                                 #
# --------------------------------------------------------------------------- #

def _load_or_create_sidecar(slug: str) -> Dict[str, Any]:
    """Load existing sidecar or create a fresh empty one."""
    sp = _sidecar_path(slug)
    existing = _read_json(sp)
    if existing:
        return existing
    now = _now_iso()
    return {
        "schema_version": 1,
        "project_slug": slug,
        "created_at": now,
        "updated_at": now,
        "adrs": [],
    }


def _save_sidecar(slug: str, sidecar: Dict[str, Any]) -> None:
    sidecar["updated_at"] = _now_iso()
    errors = _validate_sidecar(sidecar)
    if errors:
        _err("Sidecar validation failed:")
        for e in errors:
            _err(f"  {e}")
        sys.exit(4)
    _write_json_atomic(_sidecar_path(slug), sidecar)
    _mirror_to_profile(slug, sidecar)


# --------------------------------------------------------------------------- #
# Slug derivation and numbering                                               #
# --------------------------------------------------------------------------- #

def _title_to_slug(title: str) -> str:
    """Derive a kebab-case slug from an ADR title."""
    # Lowercase, replace non-alnum with hyphens, collapse runs, strip edges
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower())
    slug = slug.strip("-")
    # Cap length to keep filenames reasonable
    if len(slug) > 60:
        slug = slug[:60].rstrip("-")
    return slug


def _next_number(adrs: List[Dict[str, Any]]) -> int:
    """Return next sequential ADR number."""
    if not adrs:
        return 1
    return max(a["number"] for a in adrs) + 1


def _find_adr(adrs: List[Dict[str, Any]], number: int) -> Optional[Dict[str, Any]]:
    for a in adrs:
        if a["number"] == number:
            return a
    return None


# --------------------------------------------------------------------------- #
# ADR status transitions                                                      #
# --------------------------------------------------------------------------- #

_VALID_TRANSITIONS = {
    "proposed": ["accepted"],
    "accepted": ["deprecated", "superseded"],
    "superseded": [],
    "deprecated": [],
}


def _validate_transition(current: str, target: str) -> Optional[str]:
    """Returns error message if transition is invalid, else None."""
    allowed = _VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        return f"Cannot transition from '{current}' to '{target}'. Allowed: {allowed or '(none -- terminal state)'}"
    return None


# --------------------------------------------------------------------------- #
# Output dir resolution                                                       #
# --------------------------------------------------------------------------- #

def _resolve_adr_dir(slug: str, override: Optional[str] = None) -> Path:
    """Find the adr output directory. Prefers <repo>/docs/adr/."""
    if override:
        return Path(override).resolve() / "adr"
    profile = _load_profile(slug)
    repo = profile.get("repository_path", "")
    if repo:
        rp = Path(repo)
        if rp.is_dir():
            return rp / "docs" / "adr"
    # Fallback: staging dir next to profiles
    return PROFILES_DIR / f"{slug}_docs" / "adr"


# --------------------------------------------------------------------------- #
# ADR Markdown rendering                                                      #
# --------------------------------------------------------------------------- #

def _render_adr_md(adr: Dict[str, Any]) -> str:
    """Render a single ADR to Markdown string."""
    num_str = f"{adr['number']:04d}"
    lines = [f"# {num_str}. {adr['title']}\n"]
    lines.append(f"Date: {_human_date(adr['created_at'])}")
    lines.append(f"Status: {adr['status']}")

    if adr.get("superseded_by"):
        lines.append(f"Superseded by: [{adr['superseded_by']:04d}]({adr['superseded_by']:04d}-*.md)")
    if adr.get("supersedes"):
        lines.append(f"Supersedes: [{adr['supersedes']:04d}]({adr['supersedes']:04d}-*.md)")

    if adr.get("tags"):
        lines.append(f"Tags: {', '.join(adr['tags'])}")
    lines.append("")

    lines.append("## Context\n")
    lines.append(adr["context"])
    lines.append("")

    lines.append("## Decision\n")
    lines.append(adr["decision"])
    lines.append("")

    lines.append("## Consequences\n")
    cons = adr["consequences"]
    if cons.get("positive"):
        lines.append("### Positive\n")
        for c in cons["positive"]:
            lines.append(f"- {c}")
        lines.append("")
    if cons.get("negative"):
        lines.append("### Negative\n")
        for c in cons["negative"]:
            lines.append(f"- {c}")
        lines.append("")
    if cons.get("neutral"):
        lines.append("### Neutral\n")
        for c in cons["neutral"]:
            lines.append(f"- {c}")
        lines.append("")

    if adr.get("alternatives"):
        lines.append("## Alternatives Considered\n")
        for alt in adr["alternatives"]:
            lines.append(f"### {alt['name']}\n")
            if alt.get("description"):
                lines.append(f"- {alt['description']}")
            if alt.get("why_rejected"):
                lines.append(f"- Why rejected: {alt['why_rejected']}")
            lines.append("")

    if adr.get("notes"):
        lines.append("## Notes\n")
        lines.append(adr["notes"])
        lines.append("")

    return "\n".join(lines)


def _render_index_md(adrs: List[Dict[str, Any]], project_name: str) -> str:
    """Render the ADR index page."""
    lines = [f"# Architecture Decision Records -- {project_name}\n"]

    if not adrs:
        lines.append("_(No ADRs recorded yet.)_\n")
        lines.append("---\n")
        lines.append("_Generated by `adr-generator`_\n")
        return "\n".join(lines)

    # Group by status for display order
    status_order = ["accepted", "proposed", "superseded", "deprecated"]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for a in adrs:
        s = a["status"]
        if s not in grouped:
            grouped[s] = []
        grouped[s].append(a)

    for status in status_order:
        group = grouped.get(status, [])
        if not group:
            continue
        lines.append(f"## {status.capitalize()}\n")
        lines.append("| # | Title | Date | Tags |")
        lines.append("|---|-------|------|------|")
        for a in sorted(group, key=lambda x: x["number"]):
            num_str = f"{a['number']:04d}"
            filename = f"{num_str}-{a['slug']}.md"
            tags = ", ".join(a.get("tags", []))
            date = _human_date(a["created_at"])
            safe_title = a["title"].replace("|", "\\|")
            lines.append(f"| [{num_str}]({filename}) | {safe_title} | {date} | {tags} |")
        lines.append("")

    lines.append("---\n")
    lines.append("_Generated by `adr-generator` -- Re-render with `python scripts/adr_tool.py render <slug>`_\n")
    return "\n".join(lines)


def _adr_filename(adr: Dict[str, Any]) -> str:
    return f"{adr['number']:04d}-{adr['slug']}.md"


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_new(args: argparse.Namespace) -> int:
    """Create a new ADR."""
    slug = args.slug
    _ = _load_profile(slug)  # Verify profile exists
    payload = _read_stdin_json()

    # Validate required fields
    required = ["title", "status", "context", "decision", "consequences"]
    missing = [f for f in required if f not in payload]
    if missing:
        _err(f"Missing required fields: {', '.join(missing)}")
        return 6

    title = payload["title"]
    status = payload["status"]
    if status not in ("proposed", "accepted"):
        _err(f"New ADR status must be 'proposed' or 'accepted', got '{status}'")
        return 6

    # Validate consequences shape
    cons = payload["consequences"]
    if not isinstance(cons, dict):
        _err("'consequences' must be an object with positive/negative/neutral arrays.")
        return 6
    for key in ("positive", "negative", "neutral"):
        if key not in cons:
            cons[key] = []

    sidecar = _load_or_create_sidecar(slug)
    adrs = sidecar["adrs"]

    # Auto-number and slug
    number = _next_number(adrs)
    adr_slug = _title_to_slug(title)

    # Check slug collision
    existing_slugs = {a["slug"] for a in adrs}
    if adr_slug in existing_slugs:
        adr_slug = f"{adr_slug}-{number}"

    now = _now_iso()
    adr_entry = {
        "number": number,
        "slug": adr_slug,
        "title": title,
        "status": status,
        "created_at": now,
        "superseded_by": None,
        "supersedes": None,
        "tags": payload.get("tags", []),
        "context": payload["context"],
        "decision": payload["decision"],
        "consequences": cons,
        "alternatives": payload.get("alternatives", []),
        "notes": payload.get("notes", ""),
    }

    adrs.append(adr_entry)
    _save_sidecar(slug, sidecar)

    # Write the ADR Markdown file
    adr_dir = _resolve_adr_dir(slug)
    md_content = _render_adr_md(adr_entry)
    md_path = adr_dir / _adr_filename(adr_entry)
    _write_text_atomic(md_path, md_content)

    print(f"Created ADR {number:04d}: {title} ({status})")
    print(f"  File: {md_path}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show a single ADR."""
    slug = args.slug
    sidecar = _read_json(_sidecar_path(slug))
    if not sidecar:
        _err(f"No ADR sidecar found for '{slug}'. Create one with 'new'.")
        return 10

    number = args.number
    adr = _find_adr(sidecar["adrs"], number)
    if not adr:
        _err(f"ADR {number:04d} not found.")
        return 8

    if args.json:
        print(json.dumps(adr, indent=2))
        return 0

    # Human-readable output
    num_str = f"{number:04d}"
    status_upper = adr["status"].upper()
    print(f"  ADR {num_str}: {adr['title']}")
    print(f"  {'-' * (len(num_str) + len(adr['title']) + 6)}")
    print(f"  Status     : {status_upper}")
    print(f"  Date       : {_human_date(adr['created_at'])}")
    if adr.get("tags"):
        print(f"  Tags       : {', '.join(adr['tags'])}")
    if adr.get("superseded_by"):
        print(f"  Superseded : by ADR {adr['superseded_by']:04d}")
    if adr.get("supersedes"):
        print(f"  Supersedes : ADR {adr['supersedes']:04d}")

    print(f"\n  Context:")
    print(f"    {adr['context']}")

    print(f"\n  Decision:")
    print(f"    {adr['decision']}")

    cons = adr["consequences"]
    if cons.get("positive") or cons.get("negative") or cons.get("neutral"):
        print(f"\n  Consequences:")
        for c in cons.get("positive", []):
            print(f"    [+] {c}")
        for c in cons.get("negative", []):
            print(f"    [-] {c}")
        for c in cons.get("neutral", []):
            print(f"    [~] {c}")

    if adr.get("alternatives"):
        print(f"\n  Alternatives considered:")
        for alt in adr["alternatives"]:
            rej = f" -- rejected: {alt['why_rejected']}" if alt.get("why_rejected") else ""
            print(f"    - {alt['name']}{rej}")

    if adr.get("notes"):
        print(f"\n  Notes: {adr['notes']}")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all ADRs."""
    slug = args.slug
    sidecar = _read_json(_sidecar_path(slug))
    if not sidecar:
        _err(f"No ADR sidecar found for '{slug}'. Create one with 'new'.")
        return 10

    profile = _load_profile(slug)
    project_name = profile.get("project_name", slug)
    adrs = sidecar["adrs"]

    # Filter by status
    if args.status:
        adrs = [a for a in adrs if a["status"] == args.status]

    # Filter by tag
    if args.tag:
        adrs = [a for a in adrs if args.tag in a.get("tags", [])]

    if args.json:
        print(json.dumps(adrs, indent=2))
        return 0

    # Human-readable
    print(f"  {project_name}  ({slug}) -- Architecture Decision Records")
    print(f"  {'-' * 50}")
    print(f"  ADRs: {len(adrs)}")

    if not adrs:
        print("  (none)")
        return 0

    # Status indicators
    _STATUS_ICON = {
        "proposed": "[?]",
        "accepted": "[+]",
        "superseded": "[x]",
        "deprecated": "[-]",
    }

    for adr in sorted(adrs, key=lambda x: x["number"]):
        icon = _STATUS_ICON.get(adr["status"], "[ ]")
        tags = ""
        if adr.get("tags"):
            tags = "  (" + ", ".join(adr["tags"]) + ")"
        sup = ""
        if adr.get("superseded_by"):
            sup = f"  -> superseded by {adr['superseded_by']:04d}"
        print(f"\n  {icon}  {adr['number']:04d}  {adr['title']}  [{adr['status']}]{tags}{sup}")
        print(f"         {_human_date(adr['created_at'])}")

    return 0


def cmd_supersede(args: argparse.Namespace) -> int:
    """Mark one ADR as superseded by another."""
    slug = args.slug
    sidecar = _read_json(_sidecar_path(slug))
    if not sidecar:
        _err(f"No ADR sidecar found for '{slug}'.")
        return 10

    old_num = args.old_number
    new_num = args.new_number

    if old_num == new_num:
        _err("Old and new ADR numbers must be different.")
        return 6

    adrs = sidecar["adrs"]
    old_adr = _find_adr(adrs, old_num)
    new_adr = _find_adr(adrs, new_num)

    if not old_adr:
        _err(f"ADR {old_num:04d} not found.")
        return 8
    if not new_adr:
        _err(f"ADR {new_num:04d} not found.")
        return 8

    # Validate the old ADR can be superseded
    err = _validate_transition(old_adr["status"], "superseded")
    if err:
        _err(err)
        return 6

    # Update both entries
    old_adr["status"] = "superseded"
    old_adr["superseded_by"] = new_num
    new_adr["supersedes"] = old_num

    _save_sidecar(slug, sidecar)

    # Re-render both ADR files
    adr_dir = _resolve_adr_dir(slug)
    _write_text_atomic(adr_dir / _adr_filename(old_adr), _render_adr_md(old_adr))
    _write_text_atomic(adr_dir / _adr_filename(new_adr), _render_adr_md(new_adr))

    print(f"ADR {old_num:04d} superseded by ADR {new_num:04d}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Change the status of an ADR."""
    slug = args.slug
    sidecar = _read_json(_sidecar_path(slug))
    if not sidecar:
        _err(f"No ADR sidecar found for '{slug}'.")
        return 10

    number = args.number
    target = args.to
    adr = _find_adr(sidecar["adrs"], number)
    if not adr:
        _err(f"ADR {number:04d} not found.")
        return 8

    if adr["status"] == target:
        _err(f"ADR {number:04d} is already '{target}'.")
        return 0

    err = _validate_transition(adr["status"], target)
    if err:
        _err(err)
        return 6

    old_status = adr["status"]
    adr["status"] = target
    _save_sidecar(slug, sidecar)

    # Re-render the ADR file
    adr_dir = _resolve_adr_dir(slug)
    _write_text_atomic(adr_dir / _adr_filename(adr), _render_adr_md(adr))

    print(f"ADR {number:04d}: {old_status} -> {target}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    """Re-render all ADR Markdown files and the index."""
    slug = args.slug
    sidecar = _read_json(_sidecar_path(slug))
    if not sidecar:
        _err(f"No ADR sidecar found for '{slug}'.")
        return 10

    profile = _load_profile(slug)
    project_name = profile.get("project_name", slug)
    adr_dir = _resolve_adr_dir(slug, args.output_dir)

    adrs = sidecar["adrs"]

    # Render each ADR
    for adr in adrs:
        md_path = adr_dir / _adr_filename(adr)
        _write_text_atomic(md_path, _render_adr_md(adr))

    # Render index
    index_path = adr_dir / "index.md"
    _write_text_atomic(index_path, _render_index_md(adrs, project_name))

    print(f"Rendered {len(adrs)} ADR(s) + index to: {adr_dir}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete the ADR sidecar (preserves .md files)."""
    slug = args.slug
    sp = _sidecar_path(slug)

    if not sp.exists():
        _err(f"No ADR sidecar found for '{slug}'.")
        return 10

    if not args.yes:
        _err(f"Pass --yes to confirm deletion of {sp}. ADR .md files will NOT be deleted.")
        return 9

    sp.unlink()
    print(f"Deleted ADR sidecar for '{slug}' (Markdown files preserved).")
    return 0


# --------------------------------------------------------------------------- #
# CLI scaffolding                                                             #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="adr_tool.py",
        description="Architecture Decision Record generator for the solo-dev-suite.",
    )
    sub = p.add_subparsers(dest="command")

    # new
    sp = sub.add_parser("new", help="Create a new ADR")
    sp.add_argument("slug")
    sp.add_argument("--from-stdin", action="store_true", required=True)

    # show
    sp = sub.add_parser("show", help="Show a single ADR")
    sp.add_argument("slug")
    sp.add_argument("--number", type=int, required=True)
    sp.add_argument("--json", action="store_true")

    # list
    sp = sub.add_parser("list", help="List all ADRs")
    sp.add_argument("slug")
    sp.add_argument("--status", choices=["proposed", "accepted", "superseded", "deprecated"])
    sp.add_argument("--tag")
    sp.add_argument("--json", action="store_true")

    # supersede
    sp = sub.add_parser("supersede", help="Mark one ADR as superseded by another")
    sp.add_argument("slug")
    sp.add_argument("--old-number", type=int, required=True)
    sp.add_argument("--new-number", type=int, required=True)

    # status
    sp = sub.add_parser("status", help="Change ADR status")
    sp.add_argument("slug")
    sp.add_argument("--number", type=int, required=True)
    sp.add_argument("--to", required=True, choices=["proposed", "accepted", "superseded", "deprecated"])

    # render
    sp = sub.add_parser("render", help="Re-render all ADR files + index")
    sp.add_argument("slug")
    sp.add_argument("--output-dir")

    # delete
    sp = sub.add_parser("delete", help="Delete ADR sidecar (keeps .md files)")
    sp.add_argument("slug")
    sp.add_argument("--yes", action="store_true")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    dispatch = {
        "new": cmd_new,
        "show": cmd_show,
        "list": cmd_list,
        "supersede": cmd_supersede,
        "status": cmd_status,
        "render": cmd_render,
        "delete": cmd_delete,
    }
    handler = dispatch.get(args.command)
    if not handler:
        _err(f"Unknown command: {args.command}")
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
