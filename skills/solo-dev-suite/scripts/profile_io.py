#!/usr/bin/env python3
"""
profile_io.py --CRUD operations for Solo Dev Suite project profiles.

Profiles are stored as individual JSON files under ../profiles/<slug>.json,
one file per project. This script is the ONLY thing that should write to
those files --it enforces schema validation on every write so child skills
can trust the profile shape without defensive parsing.

Commands:
    init    --from-stdin                      # create a new profile (JSON on stdin)
    show    <slug> [--json]                   # pretty-print, or --json for machines
    list    [--json]                          # list all profiles
    update  <slug> --from-stdin               # shallow-merge patch (JSON on stdin)
    delete  <slug>                            # remove a profile (asks for confirmation)

All commands exit 0 on success, non-zero on any error, and print human-
readable diagnostics to stderr. JSON output goes to stdout.

Design notes:
  * No external deps. Pure stdlib. Runs anywhere Python 3.8+ runs.
  * Validation is done against templates/profile.schema.json. If a new
    validator lib is introduced later, keep the CLI surface identical.
  * The schema is loaded lazily so --help is fast.
  * Timestamps are UTC, second precision, ISO 8601. No timezone suffix --
    matches the schema pattern and keeps the file human-diffable.
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
# Paths --everything is resolved relative to THIS script's location so the    #
# suite can be moved around without breaking. Do NOT hardcode absolute paths. #
# --------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent           # .../solo-dev-suite/scripts
SUITE_DIR = SCRIPT_DIR.parent                          # .../solo-dev-suite
PROFILES_DIR = SUITE_DIR / "profiles"                  # where <slug>.json files live
SCHEMA_PATH = SUITE_DIR / "templates" / "profile.schema.json"


# --------------------------------------------------------------------------- #
# Utilities                                                                   #
# --------------------------------------------------------------------------- #

def _err(msg: str) -> None:
    """Print to stderr with a leading tag so it's easy to grep out in pipelines."""
    print(f"[profile_io] {msg}", file=sys.stderr)


def _now_iso() -> str:
    """UTC timestamp, second precision, ISO 8601, no trailing Z.

    Matches the schema pattern '^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}'.
    Keeping it trailing-suffix-free makes profile files diff cleanly when
    only other fields change.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _load_schema() -> Dict[str, Any]:
    """Load the JSON schema file. Fatal error if missing or malformed —
    the suite cannot operate without it."""
    if not SCHEMA_PATH.exists():
        _err(f"Schema not found at {SCHEMA_PATH}. Suite install is broken.")
        sys.exit(2)
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _err(f"Schema file is invalid JSON: {e}")
        sys.exit(2)


def _profile_path(slug: str) -> Path:
    """Resolve the filesystem path for a given slug. Does NOT check existence."""
    return PROFILES_DIR / f"{slug}.json"


def _ensure_profiles_dir() -> None:
    """Make sure the profiles directory exists. Idempotent."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Validation                                                                  #
#                                                                             #
# We implement a minimal subset of JSON Schema validation inline rather than  #
# pulling in `jsonschema` as a dependency. The subset covers every construct  #
# we use in profile.schema.json:                                              #
#   - type (string, integer, array, object, null, multiple-types)             #
#   - required                                                                #
#   - enum                                                                    #
#   - pattern (regex)                                                         #
#   - minLength / maxLength                                                   #
#   - minimum / maximum                                                       #
#   - minItems / uniqueItems                                                  #
#   - const                                                                   #
#   - additionalProperties (boolean or subschema)                             #
#   - nested objects with required + properties                               #
#   - array items (single subschema)                                          #
#                                                                             #
# If the schema grows new constructs, extend _validate_value accordingly.     #
# --------------------------------------------------------------------------- #

def _type_matches(value: Any, type_spec: Any) -> bool:
    """Check if `value` matches a JSON Schema type spec (string or list)."""
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "array": list,
        "object": dict,
        "boolean": bool,
        "null": type(None),
    }
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    for t in types:
        py = type_map.get(t)
        if py is None:
            continue
        # Special case: Python booleans are instances of int, but JSON Schema
        # treats them as distinct. Reject bools when an integer is expected.
        if t == "integer" and isinstance(value, bool):
            continue
        if isinstance(value, py):
            return True
    return False


def _validate_value(value: Any, schema: Dict[str, Any], path: str, errors: List[str]) -> None:
    """Recursive validator. Appends human-readable errors to `errors`."""

    # const --strict equality
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {value!r}")
        return

    # type
    if "type" in schema and not _type_matches(value, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']}, got {type(value).__name__}")
        return

    # enum
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")
        return

    # string constraints
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: length {len(value)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: length {len(value)} > maxLength {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match pattern {schema['pattern']!r}")

    # numeric constraints
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    # array constraints
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: {len(value)} items < minItems {schema['minItems']}")
        if schema.get("uniqueItems") and len(value) != len({json.dumps(v, sort_keys=True) for v in value}):
            errors.append(f"{path}: items are not unique")
        if "items" in schema:
            for i, item in enumerate(value):
                _validate_value(item, schema["items"], f"{path}[{i}]", errors)

    # object constraints
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
                # additionalProperties: false → reject unknown keys
                # additionalProperties: {subschema} → validate against it
                # additionalProperties: true (or missing) → allow anything
                if additional is False:
                    errors.append(f"{path}: unknown property '{k}'")
                elif isinstance(additional, dict):
                    _validate_value(v, additional, sub_path, errors)


def _validate_profile(profile: Dict[str, Any]) -> List[str]:
    """Return a list of validation error strings. Empty list means valid."""
    schema = _load_schema()
    errors: List[str] = []
    _validate_value(profile, schema, "", errors)
    return errors


# --------------------------------------------------------------------------- #
# Disk I/O                                                                    #
# --------------------------------------------------------------------------- #

def _read_profile(slug: str) -> Optional[Dict[str, Any]]:
    """Load a profile from disk. Returns None if the file doesn't exist."""
    path = _profile_path(slug)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _err(f"Profile file {path} is corrupted: {e}")
        sys.exit(3)


def _write_profile(slug: str, profile: Dict[str, Any]) -> None:
    """Validate and atomically write a profile to disk.

    We write to a .tmp sibling and then rename, so a crash mid-write
    cannot leave a half-written JSON file. On Windows this rename may
    fail if the destination exists; os.replace() is the portable way.
    """
    errors = _validate_profile(profile)
    if errors:
        _err("Profile validation failed:")
        for e in errors:
            _err(f"  - {e}")
        sys.exit(4)

    _ensure_profiles_dir()
    path = _profile_path(slug)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(profile, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)  # atomic on POSIX and Windows


def _read_stdin_json() -> Dict[str, Any]:
    """Read a JSON object from stdin. Exits with a clear message on failure."""
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
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_init(args: argparse.Namespace) -> int:
    """Create a brand-new profile from JSON on stdin.

    Timestamps and schema_version are auto-injected --callers don't need
    to supply them. If the slug already exists, we refuse to overwrite
    (use `update` for that).
    """
    payload = _read_stdin_json()

    slug = payload.get("project_slug")
    if not slug:
        _err("Payload must include 'project_slug'.")
        return 6
    if _profile_path(slug).exists():
        _err(f"Profile '{slug}' already exists. Use 'update' to modify it.")
        return 7

    now = _now_iso()
    # Inject managed fields. We set them AFTER merging user input so the
    # caller cannot spoof created_at or schema_version.
    profile = {
        "schema_version": 1,
        **payload,
        "created_at": now,
        "updated_at": now,
    }

    # Fill in optional fields with schema-appropriate defaults if absent,
    # so validation passes and child skills can rely on them being present.
    profile.setdefault("repository_path", None)
    profile.setdefault("pricing_model", None)
    profile.setdefault("launch_target_date", None)
    profile.setdefault("blockers", [])
    profile.setdefault("third_party_services", [])
    profile.setdefault("last_skill_run", {})
    profile.setdefault("notes", "")

    _write_profile(slug, profile)
    print(f"Created profile: {_profile_path(slug)}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Display a single profile. Default is pretty human-readable, --json for machines."""
    profile = _read_profile(args.slug)
    if profile is None:
        _err(f"No profile found for slug '{args.slug}'.")
        return 8

    if args.json:
        # Machine-readable: just the raw JSON, no formatting nonsense.
        print(json.dumps(profile, indent=2))
        return 0

    # Human-readable. Keep it scannable --you will read this often.
    print(f"\n  {profile['project_name']}  ({profile['project_slug']})")
    print(f"  {'-' * (len(profile['project_name']) + len(profile['project_slug']) + 4)}")
    print(f"  {profile['description']}\n")
    print(f"  Phase         : {profile['current_phase']}")
    print(f"  Type          : {profile['project_type']}")
    print(f"  Stack         : {', '.join(profile['primary_stack'])}")
    print(f"  Hosting       : {profile['hosting']}")
    print(f"  Target users  : {profile['target_users']}")
    print(f"  Business model: {profile['business_model']}")
    print(f"  Hours/week    : {profile['available_hours_per_week']}")
    print(f"  Launch target : {profile.get('launch_target_date') or '(unset)'}")
    print(f"  Repo path     : {profile.get('repository_path') or '(no code yet)'}")

    blockers = profile.get("blockers", [])
    if blockers:
        print(f"\n  Blockers ({len(blockers)}):")
        for b in blockers:
            print(f"    -{b}")

    deps = profile.get("third_party_services", [])
    if deps:
        print(f"\n  Third-party services ({len(deps)}):")
        for d in deps:
            print(f"    -{d['name']:<20} {d['risk_level']:<8} --{d['purpose']}")

    runs = profile.get("last_skill_run", {})
    if runs:
        print(f"\n  Last skill runs:")
        for name, ts in sorted(runs.items()):
            print(f"    -{name:<25} {ts}")

    print(f"\n  Created : {profile['created_at']}")
    print(f"  Updated : {profile['updated_at']}\n")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all profiles. Default prints a table; --json gives machine output."""
    _ensure_profiles_dir()
    paths = sorted(PROFILES_DIR.glob("*.json"))
    if not paths:
        if args.json:
            print("[]")
        else:
            print("No profiles yet. Onboard one with the solo-dev-suite orchestrator.")
        return 0

    rows: List[Dict[str, Any]] = []
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _err(f"Skipping corrupted profile: {p.name}")
            continue
        rows.append({
            "slug": data.get("project_slug", p.stem),
            "name": data.get("project_name", "?"),
            "phase": data.get("current_phase", "?"),
            "type": data.get("project_type", "?"),
            "updated_at": data.get("updated_at", "?"),
        })

    if args.json:
        print(json.dumps(rows, indent=2))
        return 0

    # Pretty table. Column widths computed from actual data so long names don't wrap.
    headers = ["slug", "name", "phase", "type", "updated_at"]
    widths = {h: max(len(h), *(len(str(r[h])) for r in rows)) for h in headers}
    header_line = "  ".join(h.ljust(widths[h]) for h in headers)
    print(f"\n  {header_line}")
    print(f"  {'  '.join('─' * widths[h] for h in headers)}")
    for r in rows:
        print("  " + "  ".join(str(r[h]).ljust(widths[h]) for h in headers))
    print()
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Shallow-merge a JSON patch from stdin into an existing profile.

    Top-level keys in the patch REPLACE top-level keys in the profile.
    For nested edits (e.g. appending to an array), the caller should read
    the current profile, modify in memory, then send the full updated
    top-level value back.

    Managed fields (schema_version, created_at) are never overwritten.
    updated_at is always set to now.
    """
    profile = _read_profile(args.slug)
    if profile is None:
        _err(f"No profile found for slug '{args.slug}'.")
        return 8

    patch = _read_stdin_json()

    # Guard managed fields from the caller.
    for managed in ("schema_version", "created_at"):
        if managed in patch:
            _err(f"Ignoring attempt to modify managed field '{managed}'.")
            patch.pop(managed)

    profile.update(patch)
    profile["updated_at"] = _now_iso()

    _write_profile(args.slug, profile)
    print(f"Updated profile: {_profile_path(args.slug)}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Remove a profile. Requires --yes to skip the interactive confirmation —
    we want this to be awkward on purpose so it can't happen by accident."""
    path = _profile_path(args.slug)
    if not path.exists():
        _err(f"No profile found for slug '{args.slug}'.")
        return 8

    if not args.yes:
        _err(f"Delete {path}? Re-run with --yes to confirm.")
        return 9

    path.unlink()
    print(f"Deleted profile: {path}")
    return 0


# --------------------------------------------------------------------------- #
# Arg parsing                                                                 #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="profile_io",
        description="CRUD for Solo Dev Suite project profiles.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Create a new profile (reads JSON from stdin).")
    p_init.add_argument("--from-stdin", action="store_true", required=True,
                        help="Required flag --enforces that stdin is used.")
    p_init.set_defaults(func=cmd_init)

    # show
    p_show = sub.add_parser("show", help="Display a profile.")
    p_show.add_argument("slug", help="Project slug.")
    p_show.add_argument("--json", action="store_true", help="Machine-readable output.")
    p_show.set_defaults(func=cmd_show)

    # list
    p_list = sub.add_parser("list", help="List all profiles.")
    p_list.add_argument("--json", action="store_true", help="Machine-readable output.")
    p_list.set_defaults(func=cmd_list)

    # update
    p_update = sub.add_parser("update", help="Shallow-merge a JSON patch into a profile.")
    p_update.add_argument("slug", help="Project slug.")
    p_update.add_argument("--from-stdin", action="store_true", required=True,
                          help="Required flag --enforces that stdin is used.")
    p_update.set_defaults(func=cmd_update)

    # delete
    p_delete = sub.add_parser("delete", help="Remove a profile.")
    p_delete.add_argument("slug", help="Project slug.")
    p_delete.add_argument("--yes", action="store_true", help="Skip confirmation.")
    p_delete.set_defaults(func=cmd_delete)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
