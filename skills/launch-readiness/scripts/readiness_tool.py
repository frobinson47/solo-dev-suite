#!/usr/bin/env python3
"""
readiness_tool.py — Pre-ship launch checklist gate for the launch-readiness skill.

Owns:
  * The per-project sidecar at solo-dev-suite/profiles/<slug>.readiness.json
  * The profile mirror at profile.readiness_model (updated on every write)
  * The rendered LAUNCH_READINESS.md doc

Commands:
    init     <slug> [--from-stdin] [--force]          # Build tailored checklist
    show     <slug> [--json] [--category <id>]        # Display current state
    check    <slug> --item <ID> --status <s> [--notes] # Mark a single item
    sign-off <slug> --signed-by <name> [--force]      # Gate on open blockers
    render   <slug> [--output-dir <dir>]              # Re-generate Markdown doc
    delete   <slug> [--yes]                           # Remove sidecar + rendered docs

Design notes:
  * The checklist is dynamically tailored by _build_tailored_checklist() based
    on the project's type, business model, pricing strategy, and third-party
    services. A marketing-site gets a very different checklist than a SaaS app.
  * Items are NOT auto-passed. The user must explicitly mark each one. That's
    the whole point of a launch gate.
  * Sign-off is gated on blocker items being passed/not-applicable. --force
    bypasses the gate with a loud warning.
  * Status transitions are logged in history — same status repeated = no log
    entry, to avoid noise.
  * Like scope_tool.py and pricing_tool.py, the JSON validator is inline.
    Self-contained per skill — no shared library.
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
#                                                                             #
# This skill lives at .../launch-readiness/ and the suite lives at            #
# .../solo-dev-suite/. We resolve by looking for a sibling directory,         #
# or honoring the SOLO_DEV_SUITE_DIR env var.                                 #
# --------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent       # .../launch-readiness/scripts
SKILL_DIR = SCRIPT_DIR.parent                       # .../launch-readiness
TEMPLATES_DIR = SKILL_DIR / "templates"
SCHEMA_PATH = TEMPLATES_DIR / "readiness.schema.json"
READINESS_MD_TMPL = TEMPLATES_DIR / "LAUNCH_READINESS.md.tmpl"


def _find_suite_dir() -> Path:
    """Locate solo-dev-suite. Env var wins; otherwise walk up looking for sibling."""
    env = os.environ.get("SOLO_DEV_SUITE_DIR")
    if env:
        p = Path(env).resolve()
        if p.is_dir():
            return p
    # Standard layout: sibling of the skill folder.
    sibling = SKILL_DIR.parent / "solo-dev-suite"
    if sibling.is_dir():
        return sibling
    # Walk up in case layout is nested differently.
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
    """Tagged stderr output so pipeline consumers can grep for errors."""
    print(f"[readiness_tool] {msg}", file=sys.stderr)


def _now_iso() -> str:
    """UTC ISO 8601, second precision, no trailing Z — matches schema patterns."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _human_date(iso: Optional[str]) -> str:
    """Turn an ISO timestamp into something human-readable for Markdown output."""
    if not iso:
        return "(not set)"
    try:
        dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%B %d, %Y at %H:%M UTC")
    except ValueError:
        return iso


def _profile_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.json"


def _readiness_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.readiness.json"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load a JSON file. Returns None if missing, exits if malformed."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _err(f"{path} is corrupted: {e}")
        sys.exit(3)


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON atomically via .tmp + rename so a crash can't corrupt the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_stdin_json() -> Dict[str, Any]:
    """Read a JSON object from stdin. Exits on empty/invalid input."""
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
#                                                                             #
# Duplicated intentionally. Each skill is self-contained.                     #
# --------------------------------------------------------------------------- #

def _type_matches(value: Any, type_spec: Any) -> bool:
    """Check if a value matches a JSON Schema type specification."""
    type_map = {
        "string": str, "integer": int, "number": (int, float),
        "array": list, "object": dict, "boolean": bool, "null": type(None),
    }
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    for t in types:
        py = type_map.get(t)
        if py is None:
            continue
        # Booleans are a subclass of int in Python — don't let True match "integer".
        if t == "integer" and isinstance(value, bool):
            continue
        if isinstance(value, py):
            return True
    return False


def _validate_value(value: Any, schema: Dict[str, Any], path: str, errors: List[str]) -> None:
    """Recursively validate a value against a JSON Schema fragment."""
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


def _validate_readiness(readiness: Dict[str, Any]) -> List[str]:
    """Validate the sidecar against readiness.schema.json."""
    if not SCHEMA_PATH.exists():
        _err(f"Schema not found at {SCHEMA_PATH}. Skill install is broken.")
        sys.exit(2)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors: List[str] = []
    _validate_value(readiness, schema, "", errors)
    return errors


# --------------------------------------------------------------------------- #
# Profile helpers                                                             #
# --------------------------------------------------------------------------- #

def _load_profile(slug: str) -> Dict[str, Any]:
    """Load the main profile. Exits if missing."""
    p = _profile_path(slug)
    profile = _read_json(p)
    if profile is None:
        _err(f"No profile for slug '{slug}' at {p}.")
        _err("Onboard the project via the solo-dev-suite orchestrator first.")
        sys.exit(8)
    return profile


def _mirror_to_profile(slug: str, sidecar: Dict[str, Any]) -> None:
    """Write a lean readiness summary to profile.readiness_model.

    Also updates last_skill_run so the orchestrator's staleness detector works.
    """
    profile = _load_profile(slug)

    # Count blocker items across all applicable categories.
    blockers_total = 0
    blockers_passed = 0
    for cat in sidecar["categories"]:
        if not cat["applicable"]:
            continue
        for item in cat["items"]:
            if item["severity"] == "blocker":
                blockers_total += 1
                if item["status"] in ("passed", "not-applicable"):
                    blockers_passed += 1

    blockers_remaining = blockers_total - blockers_passed
    is_shippable = (blockers_remaining == 0) or sidecar["sign_off"].get("blockers_resolved", False)

    profile["readiness_model"] = {
        "last_check_at": sidecar["updated_at"],
        "target_launch_date": sidecar["target_launch_date"],
        "blockers_total": blockers_total,
        "blockers_passed": blockers_passed,
        "blockers_remaining": blockers_remaining,
        "is_shippable": is_shippable,
    }
    profile["updated_at"] = _now_iso()
    runs = profile.get("last_skill_run", {})
    runs["launch-readiness"] = _now_iso()
    profile["last_skill_run"] = runs
    _write_json_atomic(_profile_path(slug), profile)


# --------------------------------------------------------------------------- #
# Sidecar I/O                                                                 #
# --------------------------------------------------------------------------- #

def _write_sidecar(slug: str, sidecar: Dict[str, Any]) -> None:
    """Validate and persist the readiness sidecar."""
    sidecar["updated_at"] = _now_iso()
    errors = _validate_readiness(sidecar)
    if errors:
        _err("Sidecar validation failed:")
        for e in errors:
            _err(f"  - {e}")
        sys.exit(4)
    _write_json_atomic(_readiness_path(slug), sidecar)


def _load_sidecar(slug: str) -> Dict[str, Any]:
    """Load the readiness sidecar. Exits if missing."""
    sidecar = _read_json(_readiness_path(slug))
    if sidecar is None:
        _err(f"No readiness checklist for '{slug}'. Run `readiness_tool.py init {slug}` first.")
        sys.exit(10)
    return sidecar


# --------------------------------------------------------------------------- #
# Tailored checklist builder                                                  #
#                                                                             #
# This is where the intelligence lives — dynamically assembling checklist     #
# categories and items based on the project profile. Each item has a          #
# severity ("blocker" stops the ship, "high"/"medium"/"low" are advisory)     #
# and starts as "not-checked".                                                #
# --------------------------------------------------------------------------- #

# Prefix map: category id -> ID prefix for items.
_CATEGORY_PREFIXES = {
    "auth": "AUTH",
    "error": "ERR",
    "legal": "LEG",
    "payment": "PAY",
    "email": "EML",
    "perf": "PERF",
    "seo": "SEO",
    "mobile": "MOB",
    "monitoring": "MON",
}


def _make_item(name: str, severity: str) -> Dict[str, Any]:
    """Build a checklist item dict with defaults. ID is assigned later."""
    return {
        "id": "",
        "name": name,
        "severity": severity,
        "status": "not-checked",
        "notes": "",
        "checked_at": None,
    }


def _build_base_categories() -> List[Dict[str, Any]]:
    """Build the full base checklist before tailoring.

    Every item here represents a real post-launch pain point for solo devs.
    Severity reflects how badly it bites on launch day if missing.
    """
    return [
        {
            "id": "auth",
            "name": "Auth & session security",
            "applicable": True,
            "items": [
                _make_item("Password reset via email works end-to-end", "blocker"),
                _make_item("Sessions expire after reasonable timeout", "blocker"),
                _make_item("Logout actually clears the session", "blocker"),
                _make_item("Email verification flow works (if applicable)", "high"),
                _make_item("Login rate limiting or lockout in place", "high"),
                _make_item("Password strength requirements enforced", "medium"),
            ],
        },
        {
            "id": "error",
            "name": "Error handling",
            "applicable": True,
            "items": [
                _make_item("No raw stack traces shown to users", "blocker"),
                _make_item("Custom 404 page exists", "high"),
                _make_item("Custom 500 / error page exists", "high"),
                _make_item("Form validation errors surface clearly", "high"),
                _make_item("API errors return structured JSON, not HTML", "medium"),
            ],
        },
        {
            "id": "legal",
            "name": "Legal",
            "applicable": True,
            "items": [
                _make_item("Terms of Service page published and linked", "blocker"),
                _make_item("Privacy Policy page published and linked", "blocker"),
                _make_item("Cookie consent banner (if serving EU users)", "high"),
                _make_item("Age-gate or parental consent (if applicable)", "medium"),
            ],
        },
        {
            "id": "payment",
            "name": "Payment flow",
            "applicable": True,
            "items": [
                _make_item("Successful purchase flow works end-to-end", "blocker"),
                _make_item("Failed card / payment error handled gracefully", "blocker"),
                _make_item("Subscription cancel flow works", "blocker"),
                _make_item("Refund path documented or automated", "high"),
                _make_item("Webhook idempotency verified", "high"),
                _make_item("Tax handling configured (Stripe Tax or equivalent)", "high"),
                _make_item("Receipt / invoice email sent on purchase", "medium"),
            ],
        },
        {
            "id": "email",
            "name": "Email deliverability",
            "applicable": True,
            "items": [
                _make_item("Transactional emails actually arrive (test with real inbox)", "blocker"),
                _make_item("DKIM / SPF / DMARC records set on sending domain", "high"),
                _make_item("Unsubscribe link in marketing emails", "high"),
                _make_item("Email templates render correctly in major clients", "medium"),
            ],
        },
        {
            "id": "perf",
            "name": "Performance baseline",
            "applicable": True,
            "items": [
                _make_item("Homepage loads in < 3s on simulated 3G", "high"),
                _make_item("Critical user path works on slow connections", "high"),
                _make_item("Images optimized (WebP or compressed)", "medium"),
                _make_item("No render-blocking resources in critical path", "medium"),
            ],
        },
        {
            "id": "seo",
            "name": "SEO & metadata",
            "applicable": True,
            "items": [
                _make_item("Page titles set on all key pages", "high"),
                _make_item("Meta descriptions set on key pages", "high"),
                _make_item("Open Graph tags for social sharing", "medium"),
                _make_item("robots.txt exists and is correct", "medium"),
                _make_item("sitemap.xml generated and submitted", "medium"),
                _make_item("Canonical URLs set on all pages", "low"),
            ],
        },
        {
            "id": "mobile",
            "name": "Mobile",
            "applicable": True,
            "items": [
                _make_item("Layout works at 375px viewport width", "high"),
                _make_item("Tap targets are 44px+ minimum", "high"),
                _make_item("No horizontal scroll on mobile", "high"),
                _make_item("Forms are usable on mobile keyboard", "medium"),
            ],
        },
        {
            "id": "monitoring",
            "name": "Monitoring",
            "applicable": True,
            "items": [
                _make_item("Error tracking wired up (Sentry, LogRocket, etc.)", "blocker"),
                _make_item("Uptime check pinging homepage + key API endpoints", "high"),
                _make_item("Log aggregation or at minimum log rotation configured", "high"),
                _make_item("Alerting configured for critical errors", "medium"),
            ],
        },
    ]


def _build_tailored_checklist(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Assemble a checklist tailored to this project's profile.

    Reads project_type, business_model, pricing_model, and third_party_services
    to decide which categories apply and which extra items to add.
    """
    categories = _build_base_categories()
    project_type = profile.get("project_type", "saas")
    business_model = profile.get("business_model", "")
    pricing_model = profile.get("pricing_model") or {}
    third_party = profile.get("third_party_services") or []

    # --- Tailoring: drop or modify categories based on project context --- #

    # Marketing sites don't need auth or payment flow.
    if project_type == "marketing-site":
        for cat in categories:
            if cat["id"] == "auth":
                cat["applicable"] = False
            if cat["id"] == "payment":
                cat["applicable"] = False
            # Reduce email to just "contact form works" for marketing sites.
            if cat["id"] == "email":
                cat["items"] = [
                    _make_item("Contact form sends email successfully", "high"),
                    _make_item("DKIM / SPF / DMARC records set on sending domain", "medium"),
                ]

    # Free / internal projects don't need payment flow.
    if business_model in ("free-self-hosted", "internal-only"):
        for cat in categories:
            if cat["id"] == "payment":
                cat["applicable"] = False
            # Reduce legal for internal-only (no public-facing ToS needed).
            if cat["id"] == "legal" and business_model == "internal-only":
                cat["applicable"] = False

    # --- Tailoring: add extra items based on pricing strategy --- #

    if pricing_model.get("strategy") == "freemium":
        for cat in categories:
            if cat["id"] == "payment":
                cat["items"].append(
                    _make_item("Free tier limits enforced correctly", "blocker")
                )
                cat["items"].append(
                    _make_item("Upgrade CTA visible when user hits free tier limit", "high")
                )

    if pricing_model.get("strategy") == "free-trial":
        for cat in categories:
            if cat["id"] == "payment":
                trial_days = pricing_model.get("trial_days", "N")
                cat["items"].append(
                    _make_item(f"Trial expiration after {trial_days} days works correctly", "blocker")
                )
                cat["items"].append(
                    _make_item("Trial-to-paid conversion flow works", "high")
                )

    # --- Tailoring: Stripe Connect specific items --- #

    third_party_names = []
    for svc in third_party:
        if isinstance(svc, str):
            third_party_names.append(svc.lower())
        elif isinstance(svc, dict):
            third_party_names.append(svc.get("name", "").lower())

    if any("stripe connect" in name for name in third_party_names):
        for cat in categories:
            if cat["id"] == "payment":
                cat["items"].append(
                    _make_item("Stripe Connect onboarding flow works end-to-end", "blocker")
                )
                cat["items"].append(
                    _make_item("Payout timing and minimum thresholds configured", "high")
                )

    # --- Tailoring: mobile-app specific items --- #

    if project_type == "mobile-app":
        for cat in categories:
            if cat["id"] == "mobile":
                cat["items"].append(
                    _make_item("App Store privacy manifest / nutrition label complete", "blocker")
                )
                cat["items"].append(
                    _make_item("App Store screenshots prepared for required sizes", "high")
                )
                cat["items"].append(
                    _make_item("Content rating questionnaire completed", "high")
                )

    return categories


def _assign_item_ids(categories: List[Dict[str, Any]]) -> None:
    """Auto-assign IDs to all items across all categories. Mutates in place.

    IDs are prefixed by category (AUTH01, PAY02, etc.) and never recycled.
    If an item already has a valid ID for its category, it's preserved.
    """
    for cat in categories:
        prefix = _CATEGORY_PREFIXES.get(cat["id"], cat["id"][:3].upper())
        # Collect existing valid IDs.
        existing = set()
        for item in cat["items"]:
            if isinstance(item.get("id"), str) and re.fullmatch(f"{prefix}\\d{{2,}}", item["id"]):
                existing.add(item["id"])
        # Find the highest existing counter.
        max_n = 0
        for eid in existing:
            try:
                max_n = max(max_n, int(eid[len(prefix):]))
            except ValueError:
                pass
        # Assign IDs to items that don't have one yet.
        counter = max_n
        for item in cat["items"]:
            if not (isinstance(item.get("id"), str) and re.fullmatch(f"{prefix}\\d{{2,}}", item["id"])):
                counter += 1
                item["id"] = f"{prefix}{counter:02d}"


# --------------------------------------------------------------------------- #
# Blocker counting (used in several places)                                   #
# --------------------------------------------------------------------------- #

def _count_blockers(sidecar: Dict[str, Any]) -> Tuple[int, int, int]:
    """Returns (total, passed, remaining) for blocker-severity items."""
    total = 0
    passed = 0
    for cat in sidecar["categories"]:
        if not cat["applicable"]:
            continue
        for item in cat["items"]:
            if item["severity"] == "blocker":
                total += 1
                if item["status"] in ("passed", "not-applicable"):
                    passed += 1
    return total, passed, total - passed


# --------------------------------------------------------------------------- #
# Markdown rendering                                                          #
# --------------------------------------------------------------------------- #

_STATUS_ICONS = {
    "passed": "PASS",
    "failed": "FAIL",
    "not-applicable": "N/A",
    "not-checked": "---",
}

_SEVERITY_LABELS = {
    "blocker": "BLOCKER",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


def _render_categories_block(sidecar: Dict[str, Any]) -> str:
    """Render each applicable category as a Markdown section with item table."""
    sections = []
    for cat in sidecar["categories"]:
        if not cat["applicable"]:
            continue
        lines = [f"## {cat['name']}"]
        lines.append("")
        lines.append("| ID | Item | Severity | Status | Notes |")
        lines.append("|----|------|----------|--------|-------|")
        for item in cat["items"]:
            safe_name = item["name"].replace("|", "\\|")
            safe_notes = (item.get("notes") or "").replace("|", "\\|").replace("\n", " ")
            status_display = _STATUS_ICONS.get(item["status"], item["status"])
            severity_display = _SEVERITY_LABELS.get(item["severity"], item["severity"])
            lines.append(
                f"| `{item['id']}` | {safe_name} | {severity_display} | **{status_display}** | {safe_notes} |"
            )
        lines.append("")
        sections.append("\n".join(lines))
    return "\n".join(sections)


def _render_sign_off_block(sidecar: Dict[str, Any]) -> str:
    """Render the sign-off section. Empty until signed off."""
    so = sidecar["sign_off"]
    if so["signed_at"]:
        return (
            f"**Signed off** by **{so['signed_by']}** on {_human_date(so['signed_at'])}.  \n"
            f"Blockers resolved: {'Yes' if so['blockers_resolved'] else 'No (forced)'}"
        )
    total, passed, remaining = _count_blockers(sidecar)
    if remaining > 0:
        return (
            f"**Not yet signed off.** {remaining} blocker(s) still unresolved.\n\n"
            f"Resolve all blockers, then run: `python scripts/readiness_tool.py sign-off {sidecar['project_slug']} --signed-by \"<name>\"`"
        )
    return (
        f"**All blockers passed.** Ready for sign-off.\n\n"
        f"Run: `python scripts/readiness_tool.py sign-off {sidecar['project_slug']} --signed-by \"<name>\"`"
    )


def _render_history_block(history: List[Dict[str, Any]]) -> str:
    """Render recent history entries as a readable list."""
    if not history:
        return "_(No status changes recorded yet.)_\n"
    # Show most recent first, cap at 20 entries in the doc.
    recent = list(reversed(history[-20:]))
    lines = []
    for entry in recent:
        when = _human_date(entry["at"])
        notes_suffix = f" — {entry['notes']}" if entry.get("notes") else ""
        lines.append(
            f"- **{entry['item_id']}**: {entry['old_status']} -> {entry['new_status']} "
            f"({when}){notes_suffix}"
        )
    if len(history) > 20:
        lines.append(f"\n_(Showing 20 of {len(history)} entries. Use `show --json` for full history.)_")
    return "\n".join(lines)


def _render_countdown_block(sidecar: Dict[str, Any]) -> str:
    """Render a countdown to launch if target date is set."""
    target = sidecar.get("target_launch_date")
    if not target:
        return "_(No target launch date set.)_"
    try:
        target_dt = datetime.strptime(target, "%Y-%m-%d")
        now = datetime.now()
        days = (target_dt - now).days
        if days < 0:
            return f"**Launch date was {abs(days)} day(s) ago.** Time to ship or update the target."
        elif days == 0:
            return "**Launch day is TODAY.**"
        elif days <= 7:
            return f"**{days} day(s) to launch.** Final stretch."
        elif days <= 30:
            return f"**{days} days to launch.** Resolve blockers now."
        else:
            weeks = days // 7
            return f"{days} days ({weeks} weeks) to launch."
    except ValueError:
        return f"Target launch date: {target}"


def _render_markdown(sidecar: Dict[str, Any], profile: Dict[str, Any], output_dir: Path) -> Path:
    """Render LAUNCH_READINESS.md from the sidecar. Returns the path written."""
    output_dir.mkdir(parents=True, exist_ok=True)

    total, passed, remaining = _count_blockers(sidecar)
    shippable = remaining == 0 or sidecar["sign_off"].get("blockers_resolved", False)

    target_display = sidecar.get("target_launch_date") or "_(not set)_"

    tmpl = READINESS_MD_TMPL.read_text(encoding="utf-8")
    substitutions = {
        "project_name": profile["project_name"],
        "project_slug": sidecar["project_slug"],
        "target_launch_date_display": target_display,
        "created_at_human": _human_date(sidecar["created_at"]),
        "updated_at_human": _human_date(sidecar["updated_at"]),
        "blockers_passed": str(passed),
        "blockers_total": str(total),
        "shippable_display": "YES" if shippable else "NO",
        "countdown_block": _render_countdown_block(sidecar),
        "sign_off_block": _render_sign_off_block(sidecar),
        "categories_block": _render_categories_block(sidecar),
        "history_block": _render_history_block(sidecar.get("history", [])),
    }
    md = tmpl
    for k, v in substitutions.items():
        md = md.replace("{{" + k + "}}", v)

    out_path = output_dir / "LAUNCH_READINESS.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path


def _resolve_output_dir(profile: Dict[str, Any], slug: str, override: Optional[str]) -> Path:
    """Same resolution rules as scope-guardian — repo/docs if reachable, else staging."""
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

def cmd_init(args: argparse.Namespace) -> int:
    """Build a tailored launch checklist and persist it.

    If --from-stdin is provided, the stdin JSON can include:
      - target_launch_date: override the profile's launch target
      - custom_items: [{category, name, severity}, ...] to add
      - severity_overrides: {ITEM_ID: new_severity, ...}
    """
    slug = args.slug
    profile = _load_profile(slug)

    if _readiness_path(slug).exists() and not args.force:
        _err(f"Readiness checklist already exists for '{slug}'.")
        _err("Use `check` to update items, or pass --force to re-init (destroys history).")
        return 7

    # Build the tailored checklist from the profile.
    categories = _build_tailored_checklist(profile)

    # Read optional overrides from stdin.
    target_launch_date = profile.get("launch_target_date")
    if args.from_stdin:
        overrides = _read_stdin_json()
        # Override launch date if provided.
        if "target_launch_date" in overrides:
            target_launch_date = overrides["target_launch_date"]
        # Add custom items to specified categories.
        for custom in overrides.get("custom_items", []):
            cat_id = custom.get("category", "")
            for cat in categories:
                if cat["id"] == cat_id and cat["applicable"]:
                    cat["items"].append(_make_item(
                        custom.get("name", "Custom item"),
                        custom.get("severity", "medium"),
                    ))
                    break
            else:
                _err(f"Custom item targets unknown or non-applicable category '{cat_id}'. Skipping.")
        # Apply severity overrides by item ID (after IDs are assigned below).
        # Store for post-ID-assignment application.
        severity_overrides = overrides.get("severity_overrides", {})
    else:
        severity_overrides = {}

    # Assign IDs to all items.
    _assign_item_ids(categories)

    # Apply severity overrides now that IDs exist.
    valid_severities = {"blocker", "high", "medium", "low"}
    for cat in categories:
        for item in cat["items"]:
            if item["id"] in severity_overrides:
                new_sev = severity_overrides[item["id"]]
                if new_sev in valid_severities:
                    item["severity"] = new_sev
                else:
                    _err(f"Invalid severity override '{new_sev}' for {item['id']}. Ignoring.")

    now = _now_iso()
    sidecar = {
        "schema_version": 1,
        "project_slug": slug,
        "created_at": now,
        "updated_at": now,
        "target_launch_date": target_launch_date,
        "categories": categories,
        "sign_off": {
            "blockers_resolved": False,
            "signed_at": None,
            "signed_by": None,
        },
        "history": [],
    }

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, _load_sidecar(slug))

    # Render docs immediately.
    output_dir = _resolve_output_dir(profile, slug, None)
    md_path = _render_markdown(_load_sidecar(slug), profile, output_dir)

    # Summary output.
    total, passed, remaining = _count_blockers(sidecar)
    applicable_cats = [c for c in categories if c["applicable"]]
    total_items = sum(len(c["items"]) for c in applicable_cats)
    print(f"Readiness sidecar : {_readiness_path(slug)}")
    print(f"LAUNCH_READINESS  : {md_path}")
    print(f"Categories        : {len(applicable_cats)} applicable")
    print(f"Items             : {total_items} total, {total} blockers")
    print(f"Target launch     : {target_launch_date or '(not set)'}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Display the current readiness state."""
    sidecar = _load_sidecar(args.slug)

    if args.json:
        if args.category:
            # Filter to a single category.
            cat = next((c for c in sidecar["categories"] if c["id"] == args.category), None)
            if cat is None:
                _err(f"No category '{args.category}' in checklist.")
                return 8
            print(json.dumps(cat, indent=2))
        else:
            print(json.dumps(sidecar, indent=2))
        return 0

    profile = _load_profile(args.slug)
    total, passed, remaining = _count_blockers(sidecar)

    print(f"\n  {profile['project_name']}  ({args.slug}) — Launch Readiness")
    print(f"  {'-' * (len(profile['project_name']) + len(args.slug) + 22)}")
    print(f"  Target launch : {sidecar.get('target_launch_date') or '(not set)'}")
    print(f"  Blockers      : {passed}/{total} passed ({remaining} remaining)")
    if sidecar["sign_off"]["signed_at"]:
        print(f"  Signed off    : {_human_date(sidecar['sign_off']['signed_at'])} by {sidecar['sign_off']['signed_by']}")
    else:
        print(f"  Signed off    : No")

    # Show categories (optionally filtered).
    cats_to_show = sidecar["categories"]
    if args.category:
        cats_to_show = [c for c in cats_to_show if c["id"] == args.category]
        if not cats_to_show:
            _err(f"No category '{args.category}' in checklist.")
            return 8

    for cat in cats_to_show:
        if not cat["applicable"]:
            continue
        item_count = len(cat["items"])
        done_count = sum(1 for it in cat["items"] if it["status"] in ("passed", "not-applicable"))
        print(f"\n  {cat['name']}  ({done_count}/{item_count})")
        print(f"  {'-' * (len(cat['name']) + 10)}")
        for item in cat["items"]:
            icon = {"passed": "+", "failed": "X", "not-applicable": "-", "not-checked": " "}.get(item["status"], "?")
            sev_tag = f"[{item['severity'].upper()}]" if item["severity"] == "blocker" else f"[{item['severity']}]"
            notes_suffix = f"  ({item['notes']})" if item.get("notes") else ""
            print(f"     [{icon}] {item['id']}  {item['name']}  {sev_tag}{notes_suffix}")
    print()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Mark a single checklist item with a status."""
    slug = args.slug
    sidecar = _load_sidecar(slug)

    valid_statuses = {"passed", "failed", "not-applicable", "not-checked"}
    if args.status not in valid_statuses:
        _err(f"Invalid status '{args.status}'. Must be one of: {', '.join(sorted(valid_statuses))}")
        return 4

    # Find the item by ID across all categories.
    target_item = None
    for cat in sidecar["categories"]:
        for item in cat["items"]:
            if item["id"] == args.item:
                target_item = item
                break
        if target_item:
            break

    if target_item is None:
        _err(f"No item with ID '{args.item}' in the checklist.")
        return 8

    old_status = target_item["status"]
    new_status = args.status

    # Only record history if status actually changed — avoids log noise.
    if old_status != new_status:
        target_item["status"] = new_status
        target_item["checked_at"] = _now_iso()
        if args.notes:
            target_item["notes"] = args.notes

        sidecar.setdefault("history", []).append({
            "at": _now_iso(),
            "item_id": args.item,
            "old_status": old_status,
            "new_status": new_status,
            "notes": args.notes or "",
        })

        _write_sidecar(slug, sidecar)
        _mirror_to_profile(slug, _load_sidecar(slug))

        print(f"{args.item}: {old_status} -> {new_status}")
    else:
        # Status unchanged — still update notes if provided.
        if args.notes and args.notes != target_item.get("notes", ""):
            target_item["notes"] = args.notes
            _write_sidecar(slug, sidecar)
            print(f"{args.item}: status unchanged ({old_status}), notes updated.")
        else:
            print(f"{args.item}: already {old_status}. No change.")
    return 0


def cmd_sign_off(args: argparse.Namespace) -> int:
    """Gate the ship decision on blocker resolution.

    All blocker-severity items must be passed or not-applicable before
    sign-off proceeds. --force bypasses the gate with a warning.
    """
    slug = args.slug
    sidecar = _load_sidecar(slug)

    if sidecar["sign_off"]["signed_at"]:
        _err(f"Already signed off by '{sidecar['sign_off']['signed_by']}' on {_human_date(sidecar['sign_off']['signed_at'])}.")
        _err("To re-verify, delete and re-init the checklist.")
        return 7

    # Collect unresolved blockers.
    unresolved = []
    for cat in sidecar["categories"]:
        if not cat["applicable"]:
            continue
        for item in cat["items"]:
            if item["severity"] == "blocker" and item["status"] not in ("passed", "not-applicable"):
                unresolved.append(item)

    if unresolved and not args.force:
        _err(f"Cannot sign off — {len(unresolved)} blocker(s) still unresolved:")
        for item in unresolved:
            _err(f"  - {item['id']}: {item['name']} (status: {item['status']})")
        _err("")
        _err("Resolve all blockers first, or pass --force to override.")
        return 4

    if unresolved and args.force:
        _err(f"⚠️  FORCE sign-off overriding {len(unresolved)} unresolved blocker(s):")
        for item in unresolved:
            _err(f"  - {item['id']}: {item['name']} (status: {item['status']})")

    sidecar["sign_off"]["blockers_resolved"] = len(unresolved) == 0
    sidecar["sign_off"]["signed_at"] = _now_iso()
    sidecar["sign_off"]["signed_by"] = args.signed_by

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, _load_sidecar(slug))

    # Re-render docs to include the sign-off.
    profile = _load_profile(slug)
    output_dir = _resolve_output_dir(profile, slug, None)
    _render_markdown(_load_sidecar(slug), profile, output_dir)

    forced_tag = " (FORCED — blockers overridden)" if unresolved else ""
    print(f"Signed off by {args.signed_by}{forced_tag}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    """Re-generate LAUNCH_READINESS.md from the sidecar."""
    sidecar = _load_sidecar(args.slug)
    profile = _load_profile(args.slug)
    output_dir = _resolve_output_dir(profile, args.slug, args.output_dir)
    path = _render_markdown(sidecar, profile, output_dir)
    print(f"Rendered: {path}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Remove the readiness sidecar and any staged docs."""
    path = _readiness_path(args.slug)
    if not path.exists():
        _err(f"No readiness checklist for '{args.slug}'.")
        return 8
    if not args.yes:
        _err(f"Delete readiness checklist for '{args.slug}'? Re-run with --yes to confirm.")
        return 9
    path.unlink()
    # Remove staged docs if any.
    staged = PROFILES_DIR / f"{args.slug}_docs" / "LAUNCH_READINESS.md"
    if staged.exists():
        staged.unlink()
    print(f"Deleted readiness checklist for '{args.slug}'.")
    return 0


# --------------------------------------------------------------------------- #
# Arg parsing                                                                 #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="readiness_tool",
        description="Launch Readiness pre-ship checklist gate.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # --- init --- #
    p_init = sub.add_parser("init", help="Build a tailored checklist and persist it.")
    p_init.add_argument("slug")
    p_init.add_argument("--from-stdin", action="store_true",
                        help="Read custom items / overrides from stdin JSON.")
    p_init.add_argument("--force", action="store_true",
                        help="Overwrite an existing checklist (destroys history).")
    p_init.set_defaults(func=cmd_init)

    # --- show --- #
    p_show = sub.add_parser("show", help="Display the current readiness state.")
    p_show.add_argument("slug")
    p_show.add_argument("--json", action="store_true")
    p_show.add_argument("--category", help="Filter to a specific category ID.")
    p_show.set_defaults(func=cmd_show)

    # --- check --- #
    p_check = sub.add_parser("check", help="Mark a checklist item with a status.")
    p_check.add_argument("slug")
    p_check.add_argument("--item", required=True, help="Item ID (e.g. AUTH01).")
    p_check.add_argument("--status", required=True,
                         help="New status: passed, failed, not-applicable, not-checked.")
    p_check.add_argument("--notes", default="", help="Optional notes for this check.")
    p_check.set_defaults(func=cmd_check)

    # --- sign-off --- #
    p_signoff = sub.add_parser("sign-off", help="Sign off on launch readiness (gated on blockers).")
    p_signoff.add_argument("slug")
    p_signoff.add_argument("--signed-by", required=True, help="Name of the person signing off.")
    p_signoff.add_argument("--force", action="store_true",
                           help="Override unresolved blockers (use with caution).")
    p_signoff.set_defaults(func=cmd_sign_off)

    # --- render --- #
    p_render = sub.add_parser("render", help="Re-generate LAUNCH_READINESS.md from the sidecar.")
    p_render.add_argument("slug")
    p_render.add_argument("--output-dir", help="Override the default output location.")
    p_render.set_defaults(func=cmd_render)

    # --- delete --- #
    p_delete = sub.add_parser("delete", help="Remove readiness sidecar + rendered docs.")
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
