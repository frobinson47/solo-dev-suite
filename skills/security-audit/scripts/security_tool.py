#!/usr/bin/env python3
"""
security_tool.py -- Pre-ship security audit for the security-audit skill.

Owns:
  * The per-project sidecar at solo-dev-suite/profiles/<slug>.security.json
  * The profile mirror at profile.security_model (updated on every write)
  * The rendered SECURITY_AUDIT.md doc

Commands:
    init     <slug>                                        # Build tailored checklist
    show     <slug> [--category <id>] [--json]             # Display current state
    check    <slug> --item <ID> --status <s> [--notes]     # Mark a single item
                     [--risk-rationale "..."]
    sign-off <slug> --signed-by <name> [--force]           # Gate on criticals+highs
    render   <slug> [--output-dir <path>]                  # Re-generate Markdown doc
    delete   <slug> [--yes]                                # Remove sidecar

Design notes:
  * Similar pattern to launch-readiness but with accepted-risk status and
    security-specific tailoring based on primary_stack and third_party_services.
  * The audit is a checklist, not a scanner. It doesn't read code.
  * accepted-risk requires a risk_rationale -- no silent risk acceptance.
  * Sign-off gates on both criticals AND highs being resolved.
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
SCHEMA_PATH = TEMPLATES_DIR / "security.schema.json"
SECURITY_MD_TMPL = TEMPLATES_DIR / "SECURITY_AUDIT.md.tmpl"


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
    print(f"[security_tool] {msg}", file=sys.stderr)


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


def _security_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.security.json"


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


# --------------------------------------------------------------------------- #
# JSON Schema validation (inline -- same minimal validator)                   #
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
    p = _profile_path(slug)
    profile = _read_json(p)
    if profile is None:
        _err(f"No profile for slug '{slug}' at {p}.")
        sys.exit(8)
    return profile


def _mirror_to_profile(slug: str, sidecar: Dict[str, Any]) -> None:
    """Write lean security summary to profile.security_model."""
    profile = _load_profile(slug)

    criticals_open = 0
    highs_open = 0
    accepted_risks = 0
    for cat in sidecar["categories"]:
        if not cat["applicable"]:
            continue
        for item in cat["items"]:
            if item["status"] == "accepted-risk":
                accepted_risks += 1
            elif item["status"] in ("not-checked", "failed"):
                if item["severity"] == "critical":
                    criticals_open += 1
                elif item["severity"] == "high":
                    highs_open += 1

    profile["security_model"] = {
        "last_audit_at": sidecar["updated_at"],
        "criticals_open": criticals_open,
        "highs_open": highs_open,
        "accepted_risks": accepted_risks,
        "is_signed_off": sidecar["sign_off"]["signed_at"] is not None,
    }
    if "last_skill_run" not in profile:
        profile["last_skill_run"] = {}
    profile["last_skill_run"]["security-audit"] = _now_iso()
    _write_json_atomic(_profile_path(slug), profile)


# --------------------------------------------------------------------------- #
# Sidecar I/O                                                                 #
# --------------------------------------------------------------------------- #

def _write_sidecar(slug: str, sidecar: Dict[str, Any]) -> None:
    sidecar["updated_at"] = _now_iso()
    errors = _validate_sidecar(sidecar)
    if errors:
        _err("Sidecar validation failed:")
        for e in errors:
            _err(f"  {e}")
        sys.exit(4)
    _write_json_atomic(_security_path(slug), sidecar)


def _load_sidecar(slug: str) -> Dict[str, Any]:
    sidecar = _read_json(_security_path(slug))
    if sidecar is None:
        _err(f"No security audit for '{slug}'. Run `security_tool.py init {slug}` first.")
        sys.exit(10)
    return sidecar


# --------------------------------------------------------------------------- #
# Tailored checklist builder                                                  #
# --------------------------------------------------------------------------- #

_CATEGORY_PREFIXES = {
    "secrets": "SEC",
    "auth": "AUTH",
    "input": "INP",
    "transport": "TRN",
    "api": "API",
    "frontend": "FE",
    "infra": "INF",
    "deps": "DEP",
    "data": "DAT",
    "integrations": "INT",
}


def _make_item(name: str, severity: str) -> Dict[str, Any]:
    return {
        "id": "",
        "name": name,
        "severity": severity,
        "status": "not-checked",
        "risk_rationale": "",
        "notes": "",
        "checked_at": None,
    }


def _build_base_categories() -> List[Dict[str, Any]]:
    """Build the 10-category security checklist baseline."""
    return [
        {
            "id": "secrets",
            "name": "Secret management",
            "applicable": True,
            "items": [
                _make_item("No secrets committed to git history (run git log search)", "critical"),
                _make_item(".env file in .gitignore", "critical"),
                _make_item("All secrets loaded from environment variables, not hardcoded", "critical"),
                _make_item("Production secrets differ from development secrets", "high"),
                _make_item("API keys have minimum required permissions (principle of least privilege)", "medium"),
                _make_item("Key rotation plan documented for critical secrets", "low"),
            ],
        },
        {
            "id": "auth",
            "name": "Authentication",
            "applicable": True,
            "items": [
                _make_item("Passwords hashed with bcrypt/argon2/scrypt (not MD5/SHA)", "critical"),
                _make_item("Session tokens expire after reasonable period", "critical"),
                _make_item("Password reset tokens expire (< 1 hour)", "high"),
                _make_item("Email enumeration mitigated on login/reset endpoints", "medium"),
                _make_item("Login rate limiting or account lockout in place", "high"),
                _make_item("Logout clears session server-side (not just client cookie)", "high"),
            ],
        },
        {
            "id": "input",
            "name": "Input handling",
            "applicable": True,
            "items": [
                _make_item("SQL queries use parameterized statements (no string concatenation)", "critical"),
                _make_item("User input escaped/sanitized before HTML rendering (XSS prevention)", "critical"),
                _make_item("File uploads validated: type, size, filename sanitized", "high"),
                _make_item("User-controlled paths/filenames cannot traverse directories", "high"),
                _make_item("CSRF protection on all state-changing endpoints", "high"),
            ],
        },
        {
            "id": "transport",
            "name": "Transport & storage",
            "applicable": True,
            "items": [
                _make_item("HTTPS enforced on all auth/payment/user-data pages", "critical"),
                _make_item("Cookies set with Secure, HttpOnly, SameSite flags", "high"),
                _make_item("PII encrypted at rest if stored (database-level or field-level)", "medium"),
                _make_item("HSTS header set for production domain", "medium"),
            ],
        },
        {
            "id": "api",
            "name": "API surface",
            "applicable": True,
            "items": [
                _make_item("All protected API routes require authentication", "critical"),
                _make_item("Rate limiting on public endpoints (login, signup, reset)", "high"),
                _make_item("CORS policy restricts origins to known domains (not wildcard *)", "high"),
                _make_item("API input validated and typed (reject unexpected fields/types)", "medium"),
                _make_item("API responses don't leak internal IDs/paths/stack info", "medium"),
            ],
        },
        {
            "id": "frontend",
            "name": "Frontend security",
            "applicable": True,
            "items": [
                _make_item("No API keys or secrets in client-side JavaScript bundles", "critical"),
                _make_item("Content Security Policy (CSP) header configured", "medium"),
                _make_item("No use of dangerouslySetInnerHTML / v-html with user data", "high"),
                _make_item("Third-party scripts loaded from trusted sources only", "medium"),
            ],
        },
        {
            "id": "infra",
            "name": "Infrastructure",
            "applicable": True,
            "items": [
                _make_item("Debug mode disabled in production", "critical"),
                _make_item("Admin panels not publicly accessible (IP-restricted or VPN)", "high"),
                _make_item("Error responses don't leak stack traces or internal paths", "high"),
                _make_item("Server logs don't contain passwords, tokens, or full credit card numbers", "high"),
            ],
        },
        {
            "id": "deps",
            "name": "Dependencies",
            "applicable": True,
            "items": [
                _make_item("Run npm audit / pip-audit -- no critical CVEs open", "high"),
                _make_item("Dependencies pinned to specific versions (lockfile exists)", "medium"),
                _make_item("No abandoned/unmaintained packages in critical paths", "medium"),
            ],
        },
        {
            "id": "data",
            "name": "Data handling",
            "applicable": True,
            "items": [
                _make_item("Database backups encrypted if they contain PII", "medium"),
                _make_item("User deletion actually removes data (not just soft-delete flag)", "medium"),
                _make_item("PII minimization: only collect what you need", "low"),
                _make_item("Log retention policy defined (logs don't grow forever)", "low"),
            ],
        },
        {
            "id": "integrations",
            "name": "Third-party integrations",
            "applicable": True,
            "items": [],
        },
    ]


def _has_stack_keyword(stack: List[str], keywords: List[str]) -> bool:
    """Check if any keyword appears in any stack entry (case-insensitive)."""
    stack_lower = " ".join(s.lower() for s in stack)
    return any(kw.lower() in stack_lower for kw in keywords)


def _build_tailored_checklist(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tailor the base checklist based on the project profile."""
    categories = _build_base_categories()
    project_type = profile.get("project_type", "")
    business_model = profile.get("business_model", "")
    stack = profile.get("primary_stack") or []
    services = profile.get("third_party_services") or []

    # --- Project type tailoring ---
    # Marketing sites don't need auth/api categories
    if project_type == "marketing-site":
        for cat in categories:
            if cat["id"] in ("auth", "api"):
                cat["applicable"] = False

    # --- Stack-specific items ---
    # FastAPI / Python backend
    if _has_stack_keyword(stack, ["fastapi", "flask", "django"]):
        for cat in categories:
            if cat["id"] == "api":
                cat["items"].append(_make_item(
                    "FastAPI/Flask: request body models validate input types (Pydantic/marshmallow)",
                    "medium"
                ))
            if cat["id"] == "auth":
                cat["items"].append(_make_item(
                    "Python backend: JWT tokens have expiration claim and are verified server-side",
                    "high"
                ))

    # React / frontend framework
    if _has_stack_keyword(stack, ["react", "next.js", "vue", "svelte"]):
        for cat in categories:
            if cat["id"] == "frontend":
                cat["items"].append(_make_item(
                    "React/SPA: auth tokens stored in httpOnly cookies, not localStorage",
                    "high"
                ))

    # SQLite / SQLAlchemy
    if _has_stack_keyword(stack, ["sqlite", "sqlalchemy", "prisma", "supabase"]):
        for cat in categories:
            if cat["id"] == "input":
                cat["items"].append(_make_item(
                    "ORM used for all queries (no raw SQL with string interpolation)",
                    "high"
                ))

    # Docker / homelab hosting
    if _has_stack_keyword(stack, ["docker"]) or "docker" in (profile.get("hosting") or "").lower():
        for cat in categories:
            if cat["id"] == "infra":
                cat["items"].append(_make_item(
                    "Docker containers run as non-root user",
                    "medium"
                ))
                cat["items"].append(_make_item(
                    "Docker images use specific version tags, not :latest",
                    "low"
                ))

    # --- Third-party service items ---
    integration_cat = None
    for cat in categories:
        if cat["id"] == "integrations":
            integration_cat = cat
            break

    if not services:
        # No services tracked -- mark category as not applicable
        if integration_cat:
            integration_cat["applicable"] = False
    else:
        service_names_lower = [s.get("name", "").lower() for s in services]
        all_names = " ".join(service_names_lower)

        if "stripe" in all_names:
            integration_cat["items"].append(_make_item(
                "Stripe: webhook signatures verified (stripe.webhooks.constructEvent)",
                "critical"
            ))
            integration_cat["items"].append(_make_item(
                "Stripe: publishable key in frontend, secret key server-side only",
                "critical"
            ))
            integration_cat["items"].append(_make_item(
                "Stripe: test mode keys not used in production",
                "high"
            ))

        # Generic OAuth / SSO services
        if any(kw in all_names for kw in ["auth0", "clerk", "authentik", "okta", "oauth"]):
            integration_cat["items"].append(_make_item(
                "OAuth: state parameter validated to prevent CSRF",
                "high"
            ))
            integration_cat["items"].append(_make_item(
                "OAuth: redirect URIs restricted to known domains",
                "high"
            ))

        # Supabase
        if "supabase" in all_names:
            integration_cat["items"].append(_make_item(
                "Supabase: Row Level Security (RLS) enabled on all user-data tables",
                "critical"
            ))
            integration_cat["items"].append(_make_item(
                "Supabase: anon key in frontend, service_role key server-side only",
                "critical"
            ))

        # Generic: any service with API keys
        if services:
            integration_cat["items"].append(_make_item(
                "All third-party API keys stored as env vars, not in source code",
                "critical"
            ))

        # If still no items after checks, mark not applicable
        if not integration_cat["items"]:
            integration_cat["applicable"] = False

    return categories


def _assign_item_ids(categories: List[Dict[str, Any]]) -> None:
    """Assign unique IDs to all items using category-prefix numbering."""
    for cat in categories:
        prefix = _CATEGORY_PREFIXES.get(cat["id"], cat["id"][:3].upper())
        for i, item in enumerate(cat["items"], start=1):
            item["id"] = f"{prefix}{i:02d}"


def _count_by_severity(sidecar: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    """Count open/resolved items by severity."""
    counts: Dict[str, Dict[str, int]] = {}
    resolved_statuses = {"passed", "not-applicable", "accepted-risk"}
    for cat in sidecar["categories"]:
        if not cat["applicable"]:
            continue
        for item in cat["items"]:
            sev = item["severity"]
            if sev not in counts:
                counts[sev] = {"total": 0, "open": 0, "resolved": 0}
            counts[sev]["total"] += 1
            if item["status"] in resolved_statuses:
                counts[sev]["resolved"] += 1
            else:
                counts[sev]["open"] += 1
    return counts


# --------------------------------------------------------------------------- #
# Output dir resolution                                                       #
# --------------------------------------------------------------------------- #

def _resolve_output_dir(slug: str, override: Optional[str] = None) -> Path:
    if override:
        return Path(override).resolve()
    profile = _load_profile(slug)
    repo = profile.get("repository_path", "")
    if repo:
        rp = Path(repo)
        if rp.is_dir():
            return rp / "docs"
    return PROFILES_DIR / f"{slug}_docs"


# --------------------------------------------------------------------------- #
# Markdown rendering                                                          #
# --------------------------------------------------------------------------- #

_STATUS_ICON = {
    "passed": "[+]",
    "failed": "[X]",
    "not-applicable": "[-]",
    "accepted-risk": "[!]",
    "not-checked": "[ ]",
}

_SEVERITY_TAG = {
    "critical": "[CRITICAL]",
    "high": "[HIGH]",
    "medium": "[MEDIUM]",
    "low": "[LOW]",
}


def _render_categories_block(sidecar: Dict[str, Any]) -> str:
    lines = []
    for cat in sidecar["categories"]:
        if not cat["applicable"]:
            continue
        lines.append(f"### {cat['name']}\n")
        lines.append("| Status | ID | Item | Severity |")
        lines.append("|--------|----|------|----------|")
        for item in cat["items"]:
            icon = _STATUS_ICON.get(item["status"], "[ ]")
            sev = item["severity"]
            safe_name = item["name"].replace("|", "\\|")
            notes = ""
            if item.get("risk_rationale"):
                safe_rationale = item["risk_rationale"].replace("|", "\\|")
                notes = f" _(Risk accepted: {safe_rationale})_"
            elif item.get("notes"):
                safe_notes = item["notes"].replace("|", "\\|")
                notes = f" _{safe_notes}_"
            lines.append(f"| {icon} | `{item['id']}` | {safe_name}{notes} | {sev} |")
        lines.append("")
    return "\n".join(lines) if lines else "_(No categories applicable.)_"


def _render_accepted_risks_block(sidecar: Dict[str, Any]) -> str:
    lines = []
    for cat in sidecar["categories"]:
        if not cat["applicable"]:
            continue
        for item in cat["items"]:
            if item["status"] == "accepted-risk":
                lines.append(f"- **{item['id']}**: {item['name']}")
                lines.append(f"  - Rationale: {item['risk_rationale']}")
    if not lines:
        return "_(No accepted risks.)_"
    return "\n".join(lines)


def _render_history_block(sidecar: Dict[str, Any]) -> str:
    history = sidecar.get("history", [])
    if not history:
        return "_(No changes recorded yet.)_"
    lines = []
    for entry in history[-20:]:
        lines.append(
            f"- `{entry['item_id']}` {entry['old_status']} -> {entry['new_status']} "
            f"({_human_date(entry['at'])})"
        )
        if entry.get("notes"):
            lines.append(f"  _{entry['notes']}_")
    return "\n".join(lines)


def _render_markdown(slug: str, sidecar: Dict[str, Any]) -> str:
    """Render the full SECURITY_AUDIT.md from template + sidecar data."""
    if not SECURITY_MD_TMPL.exists():
        _err(f"Template not found at {SECURITY_MD_TMPL}.")
        sys.exit(2)
    template = SECURITY_MD_TMPL.read_text(encoding="utf-8")

    profile = _load_profile(slug)
    project_name = profile.get("project_name", slug)
    counts = _count_by_severity(sidecar)

    criticals_open = counts.get("critical", {}).get("open", 0)
    highs_open = counts.get("high", {}).get("open", 0)
    accepted_risks = sum(
        1 for cat in sidecar["categories"] if cat["applicable"]
        for item in cat["items"] if item["status"] == "accepted-risk"
    )

    sign_off = sidecar["sign_off"]
    if sign_off["signed_at"]:
        sign_off_display = f"Signed by {sign_off['signed_by']} on {_human_date(sign_off['signed_at'])}"
    else:
        sign_off_display = "NOT SIGNED OFF"

    # Warnings
    warnings = []
    if criticals_open > 0:
        warnings.append(f"> **{criticals_open} CRITICAL item(s) still open.** Ship-blocking.")
    if highs_open > 0:
        warnings.append(f"> **{highs_open} HIGH item(s) still open.** Should block ship.")
    warnings_block = "\n".join(warnings) if warnings else ""

    subs = {
        "{{project_name}}": project_name,
        "{{project_slug}}": slug,
        "{{updated_at_human}}": _human_date(sidecar["updated_at"]),
        "{{criticals_open}}": str(criticals_open),
        "{{highs_open}}": str(highs_open),
        "{{accepted_risks}}": str(accepted_risks),
        "{{sign_off_display}}": sign_off_display,
        "{{warnings_block}}": warnings_block,
        "{{categories_block}}": _render_categories_block(sidecar),
        "{{accepted_risks_block}}": _render_accepted_risks_block(sidecar),
        "{{history_block}}": _render_history_block(sidecar),
    }
    result = template
    for key, val in subs.items():
        result = result.replace(key, val)
    return result


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_init(args: argparse.Namespace) -> int:
    """Build the tailored security checklist."""
    slug = args.slug
    profile = _load_profile(slug)

    # Check if sidecar already exists
    if _security_path(slug).exists() and not args.force:
        _err(f"Security audit already exists for '{slug}'. Use --force to reinitialize.")
        return 7

    categories = _build_tailored_checklist(profile)
    _assign_item_ids(categories)

    now = _now_iso()
    sidecar = {
        "schema_version": 1,
        "project_slug": slug,
        "created_at": now,
        "updated_at": now,
        "categories": categories,
        "sign_off": {
            "criticals_resolved": False,
            "highs_resolved": False,
            "accepted_risks_count": 0,
            "signed_at": None,
            "signed_by": None,
        },
        "history": [],
    }

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    # Count items
    total_items = 0
    total_critical = 0
    total_high = 0
    applicable_cats = 0
    for cat in categories:
        if cat["applicable"]:
            applicable_cats += 1
            for item in cat["items"]:
                total_items += 1
                if item["severity"] == "critical":
                    total_critical += 1
                elif item["severity"] == "high":
                    total_high += 1

    print(f"Security audit initialized for '{slug}'")
    print(f"  Categories: {applicable_cats} applicable")
    print(f"  Items: {total_items} total, {total_critical} critical, {total_high} high")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Display the current security audit state."""
    slug = args.slug
    sidecar = _load_sidecar(slug)
    profile = _load_profile(slug)
    project_name = profile.get("project_name", slug)

    if args.json:
        if args.category:
            for cat in sidecar["categories"]:
                if cat["id"] == args.category:
                    print(json.dumps(cat, indent=2))
                    return 0
            _err(f"Category '{args.category}' not found.")
            return 8
        print(json.dumps(sidecar, indent=2))
        return 0

    # Human-readable
    print(f"  {project_name}  ({slug}) -- Security Audit")
    print(f"  {'-' * 50}")

    counts = _count_by_severity(sidecar)
    for sev in ("critical", "high", "medium", "low"):
        c = counts.get(sev, {"total": 0, "open": 0})
        if c["total"] > 0:
            print(f"  {sev.upper():10s}: {c['open']} open / {c['total']} total")

    print()

    for cat in sidecar["categories"]:
        if args.category and cat["id"] != args.category:
            continue
        if not cat["applicable"]:
            continue

        print(f"  --- {cat['name']} ---")
        for item in cat["items"]:
            icon = _STATUS_ICON.get(item["status"], "[ ]")
            sev_tag = _SEVERITY_TAG.get(item["severity"], "")
            risk_note = ""
            if item["status"] == "accepted-risk" and item.get("risk_rationale"):
                risk_note = f"  (risk: {item['risk_rationale'][:60]})"
            print(f"  {icon}  {item['id']}  {item['name']}  {sev_tag}{risk_note}")
        print()

    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Mark a single security item."""
    slug = args.slug
    sidecar = _load_sidecar(slug)

    item_id = args.item
    new_status = args.status

    # Validate accepted-risk requires rationale
    if new_status == "accepted-risk" and not args.risk_rationale:
        _err("accepted-risk requires --risk-rationale. You can't silently accept risk.")
        return 11

    # Find the item
    target = None
    for cat in sidecar["categories"]:
        for item in cat["items"]:
            if item["id"] == item_id:
                target = item
                break
        if target:
            break

    if not target:
        _err(f"Item '{item_id}' not found.")
        return 8

    old_status = target["status"]
    if old_status == new_status:
        print(f"{item_id} is already '{new_status}'.")
        return 0

    target["status"] = new_status
    target["checked_at"] = _now_iso()
    if args.notes:
        target["notes"] = args.notes
    if args.risk_rationale:
        target["risk_rationale"] = args.risk_rationale

    # Log history
    sidecar["history"].append({
        "at": _now_iso(),
        "item_id": item_id,
        "old_status": old_status,
        "new_status": new_status,
        "notes": args.notes or args.risk_rationale or "",
    })

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    print(f"{item_id}: {old_status} -> {new_status}")
    return 0


def cmd_sign_off(args: argparse.Namespace) -> int:
    """Sign off on the security audit."""
    slug = args.slug
    sidecar = _load_sidecar(slug)

    counts = _count_by_severity(sidecar)
    criticals_open = counts.get("critical", {}).get("open", 0)
    highs_open = counts.get("high", {}).get("open", 0)

    if (criticals_open > 0 or highs_open > 0) and not args.force:
        _err(f"Cannot sign off: {criticals_open} critical(s) and {highs_open} high(s) still open.")
        _err("Resolve all critical and high items, or use --force to override.")
        return 12

    if (criticals_open > 0 or highs_open > 0) and args.force:
        _err(f"WARNING: Force-signing with {criticals_open} critical(s) and {highs_open} high(s) open!")
        _err("This is recorded in the audit trail.")

    accepted = sum(
        1 for cat in sidecar["categories"] if cat["applicable"]
        for item in cat["items"] if item["status"] == "accepted-risk"
    )

    sidecar["sign_off"] = {
        "criticals_resolved": criticals_open == 0,
        "highs_resolved": highs_open == 0,
        "accepted_risks_count": accepted,
        "signed_at": _now_iso(),
        "signed_by": args.signed_by,
    }

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    if accepted > 0:
        print(f"Security audit signed off by {args.signed_by} ({accepted} accepted risk(s))")
    else:
        print(f"Security audit signed off by {args.signed_by}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    """Render the SECURITY_AUDIT.md document."""
    slug = args.slug
    sidecar = _load_sidecar(slug)

    output_dir = _resolve_output_dir(slug, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "SECURITY_AUDIT.md"

    md = _render_markdown(slug, sidecar)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(md, encoding="utf-8")
    tmp.replace(output_path)

    print(f"Rendered: {output_path}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete the security audit sidecar."""
    slug = args.slug
    sp = _security_path(slug)
    if not sp.exists():
        _err(f"No security audit for '{slug}'.")
        return 10
    if not args.yes:
        _err(f"Pass --yes to confirm deletion of {sp}.")
        return 9
    sp.unlink()
    print(f"Deleted security audit sidecar for '{slug}' (profile mirror retained).")
    return 0


# --------------------------------------------------------------------------- #
# CLI scaffolding                                                             #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="security_tool.py",
        description="Pre-ship security audit for the solo-dev-suite.",
    )
    sub = p.add_subparsers(dest="command")

    # init
    sp = sub.add_parser("init", help="Build tailored security checklist")
    sp.add_argument("slug")
    sp.add_argument("--force", action="store_true")

    # show
    sp = sub.add_parser("show", help="Display audit state")
    sp.add_argument("slug")
    sp.add_argument("--category")
    sp.add_argument("--json", action="store_true")

    # check
    sp = sub.add_parser("check", help="Mark a single item")
    sp.add_argument("slug")
    sp.add_argument("--item", required=True)
    sp.add_argument("--status", required=True,
                    choices=["passed", "failed", "not-applicable", "accepted-risk", "not-checked"])
    sp.add_argument("--notes", default="")
    sp.add_argument("--risk-rationale", default="")

    # sign-off
    sp = sub.add_parser("sign-off", help="Sign off on audit")
    sp.add_argument("slug")
    sp.add_argument("--signed-by", required=True)
    sp.add_argument("--force", action="store_true")

    # render
    sp = sub.add_parser("render", help="Render SECURITY_AUDIT.md")
    sp.add_argument("slug")
    sp.add_argument("--output-dir")

    # delete
    sp = sub.add_parser("delete", help="Delete sidecar")
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
        "init": cmd_init,
        "show": cmd_show,
        "check": cmd_check,
        "sign-off": cmd_sign_off,
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
