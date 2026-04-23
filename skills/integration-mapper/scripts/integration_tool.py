#!/usr/bin/env python3
"""
integration_tool.py — Third-party service dependency mapper for the integration-mapper skill.

Owns:
  * The per-project sidecar at solo-dev-suite/profiles/<slug>.integrations.json
  * The profile mirror at profile.third_party_services (updated on every write)
  * The rendered INTEGRATIONS.md doc

Commands:
    add      <slug> --from-stdin                       # Add a new service
    update   <slug> --from-stdin                       # Modify existing (service_id in payload)
    remove   <slug> --service-id <ID> --reason "..."   # Remove from active list
    list     <slug> [--json] [--risk-min <level>]      # Show all services
    show     <slug> --service-id <ID>                  # Single service detail
    review   <slug> --service-id <ID>                  # Mark as reviewed
    render   <slug> [--output-dir <dir>]               # Re-generate INTEGRATIONS.md
    delete   <slug> [--yes]                            # Remove entire sidecar

Design notes:
  * Every mutation (add/update/remove) requires a reason and appends to change_log.
  * Risk rollup for the profile mirror is max(blast_radius, pricing_exposure,
    deprecation_risk). A service with low blast but high deprecation is still high-risk.
  * Staleness: quarterly + >90 days or monthly + >30 days since last_reviewed.
  * Services removed via 'remove' are deleted from services[] but logged in change_log.
  * 'delete' wipes the whole sidecar. Profile mirror is NOT cleared (other skills may
    reference third_party_services).
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
SCHEMA_PATH = TEMPLATES_DIR / "integrations.schema.json"
INTEGRATIONS_MD_TMPL = TEMPLATES_DIR / "INTEGRATIONS.md.tmpl"


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
    print(f"[integration_tool] {msg}", file=sys.stderr)


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


def _integrations_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.integrations.json"


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
# JSON Schema validation (inline — same minimal validator as scope_tool.py)   #
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


def _validate_integrations(data: Dict[str, Any]) -> List[str]:
    if not SCHEMA_PATH.exists():
        _err(f"Schema not found at {SCHEMA_PATH}. Skill install is broken.")
        sys.exit(2)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors: List[str] = []
    _validate_value(data, schema, "", errors)
    return errors


# --------------------------------------------------------------------------- #
# ID assignment                                                               #
# --------------------------------------------------------------------------- #

def _next_id(services: List[Dict[str, Any]]) -> str:
    """Return the next INT## ID, never recycling deleted ones."""
    max_n = 0
    for svc in services:
        sid = svc.get("id", "")
        if isinstance(sid, str) and re.fullmatch(r"INT\d{2,}", sid):
            try:
                max_n = max(max_n, int(sid[3:]))
            except ValueError:
                pass
    return f"INT{max_n + 1:02d}"


# --------------------------------------------------------------------------- #
# Risk helpers                                                                #
# --------------------------------------------------------------------------- #

# Ordering for risk levels — used for rollup (max) and filtering (>=).
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _risk_rollup(service: Dict[str, Any]) -> str:
    """Compute the single risk_level from the 3 dimensional ratings.

    Returns the max of blast_radius, pricing_exposure, deprecation_risk.
    Note: blast_radius includes 'critical' which the other two don't,
    but the ordering handles it correctly.
    """
    ratings = [
        service["blast_radius"]["rating"],
        service["pricing_exposure"]["rating"],
        service["deprecation_risk"]["rating"],
    ]
    return max(ratings, key=lambda r: _RISK_ORDER.get(r, 0))


def _is_unhedged(service: Dict[str, Any]) -> bool:
    """A service with no fallback plan and high/critical blast radius is an unhedged bet."""
    plan = (service["fallback"].get("plan") or "").strip().lower()
    no_plan = plan in ("", "none", "n/a", "tbd")
    blast = service["blast_radius"]["rating"]
    return no_plan and blast in ("high", "critical")


def _is_stale(service: Dict[str, Any]) -> bool:
    """Check if a service is overdue for review based on its cadence."""
    cadence = service.get("review_cadence", "never")
    if cadence == "never":
        return False
    last = service.get("last_reviewed")
    if not last:
        return True  # Never reviewed = stale if cadence demands it.
    try:
        last_dt = datetime.strptime(last[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return True
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    days_since = (now - last_dt).days
    if cadence == "monthly" and days_since > 30:
        return True
    if cadence == "quarterly" and days_since > 90:
        return True
    return False


# --------------------------------------------------------------------------- #
# Profile helpers                                                             #
# --------------------------------------------------------------------------- #

def _load_profile(slug: str) -> Dict[str, Any]:
    p = _profile_path(slug)
    profile = _read_json(p)
    if profile is None:
        _err(f"No profile for slug '{slug}' at {p}.")
        _err("Onboard the project via the solo-dev-suite orchestrator first.")
        sys.exit(8)
    return profile


def _mirror_to_profile(slug: str, sidecar: Dict[str, Any]) -> None:
    """Write the lean third_party_services mirror to the profile.

    Each service gets: name, purpose, risk_level (rollup), fallback (summary).
    Also updates last_skill_run.
    """
    profile = _load_profile(slug)
    mirror = []
    for svc in sidecar["services"]:
        mirror.append({
            "name": svc["name"],
            "purpose": svc["purpose"],
            "risk_level": _risk_rollup(svc),
            "fallback": svc["fallback"]["plan"] or "(none)",
        })
    profile["third_party_services"] = mirror
    profile["updated_at"] = _now_iso()
    runs = profile.get("last_skill_run", {})
    runs["integration-mapper"] = _now_iso()
    profile["last_skill_run"] = runs
    _write_json_atomic(_profile_path(slug), profile)


# --------------------------------------------------------------------------- #
# Sidecar I/O                                                                 #
# --------------------------------------------------------------------------- #

def _write_sidecar(slug: str, sidecar: Dict[str, Any]) -> None:
    sidecar["updated_at"] = _now_iso()
    errors = _validate_integrations(sidecar)
    if errors:
        _err("Sidecar validation failed:")
        for e in errors:
            _err(f"  - {e}")
        sys.exit(4)
    _write_json_atomic(_integrations_path(slug), sidecar)


def _load_sidecar(slug: str) -> Dict[str, Any]:
    sidecar = _read_json(_integrations_path(slug))
    if sidecar is None:
        _err(f"No integrations sidecar for '{slug}'. Run `integration_tool.py add {slug}` first.")
        sys.exit(10)
    return sidecar


def _load_or_create_sidecar(slug: str) -> Dict[str, Any]:
    """Load existing sidecar or create a fresh empty one (for first 'add')."""
    existing = _read_json(_integrations_path(slug))
    if existing is not None:
        return existing
    now = _now_iso()
    return {
        "schema_version": 1,
        "project_slug": slug,
        "created_at": now,
        "updated_at": now,
        "services": [],
        "change_log": [],
    }


def _find_service(sidecar: Dict[str, Any], service_id: str) -> Optional[Dict[str, Any]]:
    """Find a service by ID. Returns None if not found."""
    for svc in sidecar["services"]:
        if svc["id"] == service_id:
            return svc
    return None


# --------------------------------------------------------------------------- #
# Markdown rendering                                                          #
# --------------------------------------------------------------------------- #

def _render_risk_matrix_block(services: List[Dict[str, Any]]) -> str:
    """Render a summary table of all services sorted by risk (highest first)."""
    if not services:
        return "_(No services tracked yet.)_\n"
    sorted_svcs = sorted(services, key=lambda s: _RISK_ORDER.get(_risk_rollup(s), 0), reverse=True)
    lines = [
        "| ID | Service | Category | Blast | Pricing | Deprecation | Risk | Fallback |",
        "|----|---------|----------|-------|---------|-------------|------|----------|",
    ]
    for svc in sorted_svcs:
        rollup = _risk_rollup(svc)
        fallback_status = "Untested" if not svc["fallback"]["tested"] else "Tested"
        if not (svc["fallback"]["plan"] or "").strip():
            fallback_status = "**NONE**"
        stale_tag = " STALE" if _is_stale(svc) else ""
        unhedged_tag = " UNHEDGED" if _is_unhedged(svc) else ""
        flags = f"{stale_tag}{unhedged_tag}".strip()
        flag_col = f" ({flags})" if flags else ""
        safe_name = svc["name"].replace("|", "\\|")
        lines.append(
            f"| `{svc['id']}` | {safe_name}{flag_col} | {svc['category']} "
            f"| {svc['blast_radius']['rating']} | {svc['pricing_exposure']['rating']} "
            f"| {svc['deprecation_risk']['rating']} | **{rollup.upper()}** | {fallback_status} |"
        )
    return "\n".join(lines)


def _render_services_block(services: List[Dict[str, Any]]) -> str:
    """Render detailed sections for each service."""
    if not services:
        return "_(No services.)_\n"
    sections = []
    for svc in services:
        rollup = _risk_rollup(svc)
        lines = [f"### {svc['name']}  (`{svc['id']}`)\n"]
        lines.append(f"**Category**: {svc['category']}  ")
        lines.append(f"**Purpose**: {svc['purpose']}  ")
        lines.append(f"**Added**: {_human_date(svc['added_at'])}  ")
        lines.append(f"**Overall risk**: {rollup.upper()}\n")

        lines.append(f"| Dimension | Rating | Detail |")
        lines.append(f"|-----------|--------|--------|")
        br_rationale = svc['blast_radius']['rationale'].replace('|', '\\|')
        lines.append(f"| Blast radius | {svc['blast_radius']['rating']} | {br_rationale} |")
        pe = svc['pricing_exposure']
        pe_notes = pe['notes'].replace('|', '\\|')
        lines.append(f"| Pricing exposure | {pe['rating']} | ${pe['current_cost_usd_per_month']}/mo — {pe_notes} |")
        dr_notes = svc['deprecation_risk']['notes'].replace('|', '\\|')
        lines.append(f"| Deprecation risk | {svc['deprecation_risk']['rating']} | {dr_notes} |")
        lines.append("")

        fb = svc["fallback"]
        tested_tag = "Tested" if fb["tested"] else "Not tested"
        lines.append(f"**Fallback**: {fb['plan'] or '(none)'}  ")
        lines.append(f"**Fallback status**: {tested_tag}  ")
        if fb["notes"]:
            lines.append(f"**Fallback notes**: {fb['notes']}  ")

        lines.append(f"\n**Review cadence**: {svc['review_cadence']}  ")
        lines.append(f"**Last reviewed**: {_human_date(svc.get('last_reviewed'))}")
        if _is_stale(svc):
            lines.append(f"\n> **STALE** — this service is overdue for review.")
        if _is_unhedged(svc):
            lines.append(f"\n> **UNHEDGED BET** — high/critical blast radius with no fallback plan.")
        if svc.get("notes"):
            lines.append(f"\n_Notes: {svc['notes']}_")
        lines.append("")
        sections.append("\n".join(lines))
    return "\n---\n\n".join(sections)


def _render_warnings_block(services: List[Dict[str, Any]]) -> str:
    """Surface unhedged bets and stale reviews prominently."""
    warnings = []
    for svc in services:
        if _is_unhedged(svc):
            warnings.append(
                f"**UNHEDGED BET**: `{svc['id']}` {svc['name']} — "
                f"{svc['blast_radius']['rating']} blast radius with no fallback plan."
            )
        if _is_stale(svc):
            warnings.append(
                f"**STALE**: `{svc['id']}` {svc['name']} — "
                f"review cadence is {svc['review_cadence']} but last reviewed {_human_date(svc.get('last_reviewed'))}."
            )
    if not warnings:
        return "_(No warnings. All services have fallback plans and are up to date on reviews.)_"
    return "\n\n".join(warnings)


def _render_change_log_block(change_log: List[Dict[str, Any]]) -> str:
    if not change_log:
        return "_(No changes recorded yet.)_\n"
    recent = list(reversed(change_log[-20:]))
    lines = []
    for entry in recent:
        when = _human_date(entry["at"])
        lines.append(
            f"- **{entry['action'].upper()}** `{entry['service_id']}` ({when}) — "
            f"{entry['change']}. Reason: {entry['reason']}"
        )
    if len(change_log) > 20:
        lines.append(f"\n_(Showing 20 of {len(change_log)} entries.)_")
    return "\n".join(lines)


def _render_markdown(sidecar: Dict[str, Any], profile: Dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    services = sidecar["services"]
    unhedged = sum(1 for s in services if _is_unhedged(s))
    stale = sum(1 for s in services if _is_stale(s))

    tmpl = INTEGRATIONS_MD_TMPL.read_text(encoding="utf-8")
    substitutions = {
        "project_name": profile["project_name"],
        "project_slug": sidecar["project_slug"],
        "service_count": str(len(services)),
        "updated_at_human": _human_date(sidecar["updated_at"]),
        "unhedged_count": str(unhedged),
        "stale_count": str(stale),
        "warnings_block": _render_warnings_block(services),
        "risk_matrix_block": _render_risk_matrix_block(services),
        "services_block": _render_services_block(services),
        "change_log_block": _render_change_log_block(sidecar.get("change_log", [])),
    }
    md = tmpl
    for k, v in substitutions.items():
        md = md.replace("{{" + k + "}}", v)

    out_path = output_dir / "INTEGRATIONS.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path


def _resolve_output_dir(profile: Dict[str, Any], slug: str, override: Optional[str]) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    repo_path = profile.get("repository_path")
    if repo_path:
        repo = Path(repo_path).expanduser()
        if repo.is_dir():
            return repo / "docs"
        _err(f"Repo path {repo} not reachable — falling back to staging.")
    return PROFILES_DIR / f"{slug}_docs"


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_add(args: argparse.Namespace) -> int:
    """Add a new third-party service to the integration map.

    Stdin shape:
        {
          "reason": "why we're adding this",
          "service": { ...service object without id/added_at... }
        }
    """
    slug = args.slug
    _load_profile(slug)  # Fail early if no profile.
    sidecar = _load_or_create_sidecar(slug)
    payload = _read_stdin_json()

    reason = (payload.get("reason") or "").strip()
    if not reason:
        _err("Payload must include a non-empty 'reason'.")
        return 11

    service_in = payload.get("service")
    if not isinstance(service_in, dict):
        _err("Payload must include a 'service' object.")
        return 6

    # Check for duplicate name (case-insensitive).
    name = service_in.get("name", "")
    for existing in sidecar["services"]:
        if existing["name"].lower() == name.lower():
            _err(f"Service '{name}' already exists as {existing['id']}. Use 'update' to modify.")
            return 7

    now = _now_iso()
    new_id = _next_id(sidecar["services"])

    # Build the full service record with managed fields.
    service = {
        "id": new_id,
        "added_at": now,
        "last_reviewed": now,
        "notes": "",
        **service_in,
    }
    # Ensure id and added_at aren't overridden by caller.
    service["id"] = new_id
    service["added_at"] = now

    sidecar["services"].append(service)
    sidecar["change_log"].append({
        "at": now,
        "action": "added",
        "service_id": new_id,
        "change": f"Added {name} ({service_in.get('category', 'other')})",
        "reason": reason,
    })

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, _load_sidecar(slug))

    risk = _risk_rollup(service)
    print(f"Added {new_id}: {name} (risk: {risk})")
    if _is_unhedged(service):
        _err(f"  UNHEDGED BET — high/critical blast radius with no fallback plan.")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Update an existing service. Payload must include service_id and reason.

    Only provided fields in 'updates' are changed; omitted fields keep current values.
    Stdin shape:
        {
          "service_id": "INT01",
          "reason": "why we're changing this",
          "updates": { ...partial service fields... }
        }
    """
    slug = args.slug
    sidecar = _load_sidecar(slug)
    payload = _read_stdin_json()

    service_id = (payload.get("service_id") or "").strip()
    reason = (payload.get("reason") or "").strip()
    if not service_id or not reason:
        _err("Payload must include non-empty 'service_id' and 'reason'.")
        return 11

    service = _find_service(sidecar, service_id)
    if service is None:
        _err(f"No service with ID '{service_id}'.")
        return 8

    updates = payload.get("updates", {})
    if not isinstance(updates, dict) or not updates:
        _err("Payload must include a non-empty 'updates' object.")
        return 6

    # Track what changed for the change_log.
    changed_fields = []
    # Protected fields that can't be overwritten by the caller.
    protected = {"id", "added_at"}

    for key, value in updates.items():
        if key in protected:
            continue
        if key in service:
            # For nested objects, merge rather than replace.
            if isinstance(service[key], dict) and isinstance(value, dict):
                service[key].update(value)
            else:
                service[key] = value
            changed_fields.append(key)
        else:
            _err(f"Unknown field '{key}' — skipping.")

    if not changed_fields:
        _err("No valid fields to update.")
        return 6

    sidecar["change_log"].append({
        "at": _now_iso(),
        "action": "updated",
        "service_id": service_id,
        "change": f"Updated {', '.join(changed_fields)} on {service['name']}",
        "reason": reason,
    })

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, _load_sidecar(slug))

    print(f"Updated {service_id}: {', '.join(changed_fields)}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    """Remove a service from the active list. Keeps it in change_log for audit."""
    slug = args.slug
    sidecar = _load_sidecar(slug)

    reason = (args.reason or "").strip()
    if not reason:
        _err("--reason is required when removing a service.")
        return 11

    service = _find_service(sidecar, args.service_id)
    if service is None:
        _err(f"No service with ID '{args.service_id}'.")
        return 8

    name = service["name"]
    sidecar["services"] = [s for s in sidecar["services"] if s["id"] != args.service_id]

    sidecar["change_log"].append({
        "at": _now_iso(),
        "action": "removed",
        "service_id": args.service_id,
        "change": f"Removed {name}",
        "reason": reason,
    })

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, _load_sidecar(slug))

    print(f"Removed {args.service_id}: {name}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Show all tracked services with risk indicators and staleness flags."""
    sidecar = _load_sidecar(args.slug)
    services = sidecar["services"]

    # Apply risk filter if specified.
    if args.risk_min:
        min_level = _RISK_ORDER.get(args.risk_min, 0)
        services = [s for s in services if _RISK_ORDER.get(_risk_rollup(s), 0) >= min_level]

    if args.json:
        print(json.dumps(services, indent=2))
        return 0

    profile = _load_profile(args.slug)
    print(f"\n  {profile['project_name']}  ({args.slug}) — Integration Map")
    print(f"  {'-' * (len(profile['project_name']) + len(args.slug) + 20)}")
    print(f"  Services: {len(services)}")

    if not services:
        print("  (none)")
        print()
        return 0

    # Sort by risk descending.
    sorted_svcs = sorted(services, key=lambda s: _RISK_ORDER.get(_risk_rollup(s), 0), reverse=True)
    for svc in sorted_svcs:
        rollup = _risk_rollup(svc)
        flags = []
        if _is_unhedged(svc):
            flags.append("UNHEDGED")
        if _is_stale(svc):
            flags.append("STALE")
        flag_str = f"  !! {', '.join(flags)}" if flags else ""
        print(f"\n  {svc['id']}  {svc['name']}  [{rollup.upper()}]{flag_str}")
        print(f"    Category: {svc['category']}  |  Blast: {svc['blast_radius']['rating']}  "
              f"|  Pricing: {svc['pricing_exposure']['rating']}  |  Deprecation: {svc['deprecation_risk']['rating']}")
        fb_plan = svc["fallback"]["plan"] or "(none)"
        tested = "tested" if svc["fallback"]["tested"] else "untested"
        print(f"    Fallback: {fb_plan} ({tested})")
        print(f"    Review: {svc['review_cadence']}  |  Last: {_human_date(svc.get('last_reviewed'))}")
    print()
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show full detail for a single service."""
    sidecar = _load_sidecar(args.slug)
    service = _find_service(sidecar, args.service_id)
    if service is None:
        _err(f"No service with ID '{args.service_id}'.")
        return 8

    if args.json:
        print(json.dumps(service, indent=2))
        return 0

    rollup = _risk_rollup(service)
    print(f"\n  {service['name']}  ({service['id']})")
    print(f"  {'-' * (len(service['name']) + len(service['id']) + 4)}")
    print(f"  Category       : {service['category']}")
    print(f"  Purpose        : {service['purpose']}")
    print(f"  Added          : {_human_date(service['added_at'])}")
    print(f"  Overall risk   : {rollup.upper()}")
    print(f"  Blast radius   : {service['blast_radius']['rating']} — {service['blast_radius']['rationale']}")
    pe = service["pricing_exposure"]
    print(f"  Pricing risk   : {pe['rating']} — ${pe['current_cost_usd_per_month']}/mo, {pe['notes']}")
    print(f"  Deprecation    : {service['deprecation_risk']['rating']} — {service['deprecation_risk']['notes']}")
    fb = service["fallback"]
    tested = "tested" if fb["tested"] else "NOT tested"
    print(f"  Fallback       : {fb['plan'] or '(none)'} ({tested})")
    if fb["notes"]:
        print(f"  Fallback notes : {fb['notes']}")
    print(f"  Review cadence : {service['review_cadence']}")
    print(f"  Last reviewed  : {_human_date(service.get('last_reviewed'))}")
    if _is_stale(service):
        print(f"  !! STALE — overdue for review")
    if _is_unhedged(service):
        print(f"  !! UNHEDGED BET — no fallback for high/critical blast radius")
    if service.get("notes"):
        print(f"  Notes          : {service['notes']}")
    print()
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    """Mark a service as reviewed (updates last_reviewed timestamp)."""
    slug = args.slug
    sidecar = _load_sidecar(slug)
    service = _find_service(sidecar, args.service_id)
    if service is None:
        _err(f"No service with ID '{args.service_id}'.")
        return 8

    now = _now_iso()
    service["last_reviewed"] = now

    sidecar["change_log"].append({
        "at": now,
        "action": "reviewed",
        "service_id": args.service_id,
        "change": f"Reviewed {service['name']}",
        "reason": "periodic review",
    })

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, _load_sidecar(slug))

    print(f"Reviewed {args.service_id}: {service['name']} (next review per {service['review_cadence']} cadence)")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    sidecar = _load_sidecar(args.slug)
    profile = _load_profile(args.slug)
    output_dir = _resolve_output_dir(profile, args.slug, args.output_dir)
    path = _render_markdown(sidecar, profile, output_dir)
    print(f"Rendered: {path}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Remove the entire integrations sidecar. Profile mirror is NOT cleared."""
    path = _integrations_path(args.slug)
    if not path.exists():
        _err(f"No integrations sidecar for '{args.slug}'.")
        return 8
    if not args.yes:
        _err(f"Delete integrations for '{args.slug}'? Re-run with --yes to confirm.")
        _err("Note: profile.third_party_services is NOT cleared.")
        return 9
    path.unlink()
    staged = PROFILES_DIR / f"{args.slug}_docs" / "INTEGRATIONS.md"
    if staged.exists():
        staged.unlink()
    print(f"Deleted integrations sidecar for '{args.slug}' (profile mirror retained).")
    return 0


# --------------------------------------------------------------------------- #
# Arg parsing                                                                 #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="integration_tool",
        description="Third-party integration dependency mapper.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add a new service (reads JSON on stdin).")
    p_add.add_argument("slug")
    p_add.add_argument("--from-stdin", action="store_true", required=True)
    p_add.set_defaults(func=cmd_add)

    p_update = sub.add_parser("update", help="Update an existing service (reads JSON on stdin).")
    p_update.add_argument("slug")
    p_update.add_argument("--from-stdin", action="store_true", required=True)
    p_update.set_defaults(func=cmd_update)

    p_remove = sub.add_parser("remove", help="Remove a service from active list.")
    p_remove.add_argument("slug")
    p_remove.add_argument("--service-id", required=True)
    p_remove.add_argument("--reason", required=True)
    p_remove.set_defaults(func=cmd_remove)

    p_list = sub.add_parser("list", help="Show all tracked services.")
    p_list.add_argument("slug")
    p_list.add_argument("--json", action="store_true")
    p_list.add_argument("--risk-min", choices=["low", "medium", "high", "critical"],
                        help="Filter to services at or above this risk level.")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Show detail for a single service.")
    p_show.add_argument("slug")
    p_show.add_argument("--service-id", required=True)
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_review = sub.add_parser("review", help="Mark a service as reviewed.")
    p_review.add_argument("slug")
    p_review.add_argument("--service-id", required=True)
    p_review.set_defaults(func=cmd_review)

    p_render = sub.add_parser("render", help="Re-generate INTEGRATIONS.md.")
    p_render.add_argument("slug")
    p_render.add_argument("--output-dir")
    p_render.set_defaults(func=cmd_render)

    p_delete = sub.add_parser("delete", help="Remove entire integrations sidecar.")
    p_delete.add_argument("slug")
    p_delete.add_argument("--yes", action="store_true")
    p_delete.set_defaults(func=cmd_delete)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
