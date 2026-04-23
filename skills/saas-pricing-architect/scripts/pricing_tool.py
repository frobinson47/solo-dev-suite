#!/usr/bin/env python3
"""
pricing_tool.py -- Versioned pricing CRUD for the saas-pricing-architect skill.

Owns:
  * The per-project sidecar at solo-dev-suite/profiles/<slug>.pricing.json
  * The profile mirror at profile.pricing_model (updated on every write)
  * The rendered PRICING.md doc

Commands:
    design   <slug> --from-stdin          # Create version 1 from JSON on stdin
    show     <slug> [--version N] [--json]  # Display active or specific version
    iterate  <slug> --from-stdin          # Create a new version, archive prior
    render   <slug> [--output-dir <dir>]  # Re-generate PRICING.md from sidecar
    delete   <slug> [--yes]               # Remove sidecar + rendered docs

Design notes:
  * Sidecar is the source of truth. profile.pricing_model is a lightweight
    summary mirror -- other skills can read it cheaply without parsing versions.
  * Version numbers are auto-assigned, monotonically increasing.
  * Archiving is automatic: when a new version becomes active, the prior
    one gets its active_until stamped with the transition time.
  * Competitive anchors are tracked at the sidecar root (not per-version)
    because they describe the market at each decision point -- competitors
    don't belong to a single pricing iteration.
  * Like scope_tool.py, the JSON validator is inline. Self-contained per skill.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


# --------------------------------------------------------------------------- #
# Path discovery                                                              #
# --------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent       # .../saas-pricing-architect/scripts
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
SCHEMA_PATH = TEMPLATES_DIR / "pricing.schema.json"
PRICING_MD_TMPL = TEMPLATES_DIR / "PRICING.md.tmpl"


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
    print(f"[pricing_tool] {msg}", file=sys.stderr)


def _now_iso() -> str:
    """UTC ISO 8601, second precision, no trailing Z -- matches the schema patterns."""
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


def _pricing_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.pricing.json"


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
# JSON Schema validation (same minimal inline validator as scope_tool.py)     #
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


def _validate_pricing(pricing: Dict[str, Any]) -> List[str]:
    if not SCHEMA_PATH.exists():
        _err(f"Schema not found at {SCHEMA_PATH}. Skill install is broken.")
        sys.exit(2)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors: List[str] = []
    _validate_value(pricing, schema, "", errors)
    return errors


# --------------------------------------------------------------------------- #
# Strategy-specific validation                                                #
#                                                                             #
# JSON Schema can't easily express "if strategy is freemium, free_tier must   #
# be non-null" type rules. We enforce these cross-field constraints here,     #
# returning the same error-list contract as the schema validator.             #
# --------------------------------------------------------------------------- #

def _validate_strategy_consistency(version: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    strategy = version.get("strategy")
    if strategy == "freemium" and version.get("free_tier") is None:
        errors.append("strategy=freemium requires a non-null free_tier definition")
    if strategy == "free-trial" and not version.get("trial_days"):
        errors.append("strategy=free-trial requires trial_days > 0")
    if strategy == "paid-only":
        if version.get("trial_days"):
            errors.append("strategy=paid-only should not have trial_days set")
        if version.get("free_tier") is not None:
            errors.append("strategy=paid-only should not have a free_tier")
    return errors


def _validate_tier_pricing_math(version: Dict[str, Any]) -> List[str]:
    """Sanity checks on tier prices. Not hard failures -- warnings to surface.

    Returns a list of warning strings (not errors). The caller decides whether
    to block or just print.
    """
    warnings: List[str] = []
    tiers = version.get("tiers", [])
    discount = version.get("annual_discount_percent", 0)

    # Tiers should be ordered by price ascending. Warn if not.
    prices = [t.get("monthly_price_usd", 0) for t in tiers]
    if prices != sorted(prices):
        warnings.append(
            "Tiers are not in ascending price order. Data is typically stored ascending; "
            "display flips to anchor-high in PRICING.md."
        )

    # Annual math check -- does the annual price roughly match the stated discount?
    for t in tiers:
        m = t.get("monthly_price_usd", 0)
        a = t.get("annual_price_usd", 0)
        if m == 0:
            continue
        implied_months = a / m if m else 0
        # A 17% discount means 9.96 months of revenue for 12 months of access.
        # Allow a sloppy range (roughly 9.5 to 11 months) so rounded prices pass.
        expected_months = 12 * (1 - discount / 100)
        if not (expected_months - 1.0 <= implied_months <= expected_months + 1.5):
            warnings.append(
                f"Tier '{t.get('name')}': annual ${a} vs monthly ${m} implies "
                f"{implied_months:.1f} months of revenue, but {discount}% discount expects "
                f"~{expected_months:.1f}. Check the annual price."
            )
    return warnings


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
    """Write a lean summary of the active pricing version to profile.pricing_model.

    This is what other skills consume. Full version history stays in the sidecar.
    """
    profile = _load_profile(slug)
    active_v = _active_version(sidecar)
    summary = {
        "active_version": active_v["version"],
        "strategy": active_v["strategy"],
        "billing_unit": active_v["billing_unit"],
        "trial_days": active_v.get("trial_days"),
        "tier_summary": [
            {
                "name": t["name"],
                "monthly_price_usd": t["monthly_price_usd"],
                "annual_price_usd": t["annual_price_usd"],
            }
            for t in active_v["tiers"]
        ],
        "annual_discount_percent": active_v["annual_discount_percent"],
    }
    profile["pricing_model"] = summary
    profile["updated_at"] = _now_iso()
    # Also record the skill run on the profile.
    runs = profile.get("last_skill_run", {})
    runs["saas-pricing-architect"] = _now_iso()
    profile["last_skill_run"] = runs
    _write_json_atomic(_profile_path(slug), profile)


# --------------------------------------------------------------------------- #
# Sidecar helpers                                                             #
# --------------------------------------------------------------------------- #

def _active_version(sidecar: Dict[str, Any]) -> Dict[str, Any]:
    """Return the version object that matches active_version. Exits if inconsistent."""
    target = sidecar["active_version"]
    for v in sidecar["versions"]:
        if v["version"] == target:
            return v
    _err(f"Inconsistent sidecar: active_version={target} not found in versions[].")
    sys.exit(12)


def _load_sidecar(slug: str) -> Dict[str, Any]:
    sidecar = _read_json(_pricing_path(slug))
    if sidecar is None:
        _err(f"No pricing file for '{slug}'. Run `pricing_tool.py design {slug}` first.")
        sys.exit(10)
    return sidecar


def _write_sidecar(slug: str, sidecar: Dict[str, Any]) -> None:
    """Validate + write. Enforces both schema and strategy-consistency rules."""
    sidecar["updated_at"] = _now_iso()

    errors = _validate_pricing(sidecar)
    # Also run per-version strategy consistency checks on the active version.
    active = next((v for v in sidecar.get("versions", []) if v.get("version") == sidecar.get("active_version")), None)
    if active:
        errors.extend(_validate_strategy_consistency(active))
    if errors:
        _err("Pricing validation failed:")
        for e in errors:
            _err(f"  - {e}")
        sys.exit(4)

    # Warnings are printed but don't block the write.
    if active:
        warnings = _validate_tier_pricing_math(active)
        for w in warnings:
            _err(f"⚠️  {w}")

    _write_json_atomic(_pricing_path(slug), sidecar)


# --------------------------------------------------------------------------- #
# Markdown rendering                                                          #
# --------------------------------------------------------------------------- #

def _format_usd(amount: float) -> str:
    """Render USD with no decimals for whole numbers, 2 decimals otherwise."""
    if amount == int(amount):
        return f"${int(amount)}"
    return f"${amount:.2f}"


def _format_limits(limits: Dict[str, Any]) -> str:
    """Turn a limits dict into a readable snippet. null values become 'unlimited'."""
    if not limits:
        return "_no limits defined_"
    parts = []
    for k, v in limits.items():
        label = k.replace("_", " ")
        if v is None:
            parts.append(f"**Unlimited {label}**")
        elif isinstance(v, bool):
            parts.append(f"**{label}**" if v else f"~~{label}~~")
        else:
            parts.append(f"**{v}** {label}")
    return " · ".join(parts)


def _render_offer_block(version: Dict[str, Any]) -> str:
    """The big 'what you're buying' section at the top."""
    lines = []
    strategy = version["strategy"]
    if strategy == "freemium":
        ft = version["free_tier"]
        lines.append(f"**Free forever** -- `{ft['name']}` tier:")
        lines.append(f"- _{ft.get('tagline', '')}_")
        for f in ft.get("features", []):
            lines.append(f"- {f}")
        if ft.get("limits"):
            lines.append(f"- Limits: {_format_limits(ft['limits'])}")
        if ft.get("upgrade_trigger"):
            lines.append(f"- **Upgrade moment**: {ft['upgrade_trigger']}")
    elif strategy == "free-trial":
        lines.append(f"**{version['trial_days']}-day free trial** on all tiers. No card required to start trial unless noted below.")
    else:
        lines.append("**Paid from day one.** No free tier, no trial.")
    return "\n".join(lines)


def _render_tiers_block(version: Dict[str, Any]) -> str:
    """Render tiers in anchor-high order (highest price first) as a sequence of cards."""
    tiers_sorted = sorted(version["tiers"], key=lambda t: t.get("monthly_price_usd", 0), reverse=True)
    chunks = []
    for t in tiers_sorted:
        highlight = " ⭐" if t.get("highlighted") else ""
        monthly = _format_usd(t["monthly_price_usd"])
        annual = _format_usd(t["annual_price_usd"])
        chunks.append(f"### {t['name']}{highlight}")
        if t.get("tagline"):
            chunks.append(f"_{t['tagline']}_\n")
        chunks.append(f"**{monthly}/month**  ·  **{annual}/year**  ·  _Target: {t['target_segment']}_")
        chunks.append("")
        chunks.append("**Includes:**")
        for f in t.get("features", []):
            chunks.append(f"- {f}")
        if t.get("limits"):
            chunks.append(f"\n**Limits:** {_format_limits(t['limits'])}")
        chunks.append("")
        chunks.append("---")
        chunks.append("")
    # Drop the trailing separator.
    while chunks and chunks[-1] in ("", "---"):
        chunks.pop()
    return "\n".join(chunks)


def _render_trial_block(version: Dict[str, Any]) -> str:
    if version["strategy"] == "free-trial":
        return f" ({version['trial_days']}-day trial)"
    return ""


def _render_launch_strategy_block(version: Dict[str, Any]) -> str:
    """If pricing is early-adopter or beta, callout the steady-state plan."""
    ls = version.get("launch_strategy", {})
    mode = ls.get("mode", "steady-state")
    if mode == "steady-state":
        return "_These are steady-state prices -- no early-adopter discount active._\n"
    lines = []
    if mode == "beta":
        lines.append("> 🧪 **Beta pricing active.** These prices may change before GA.")
    else:
        lines.append("> 🚀 **Early-adopter pricing active.**")
    discount = ls.get("discount_vs_steady_state_percent")
    if discount:
        lines.append(f"> Currently **{discount}%** below steady-state.")
    end_date = ls.get("steady_state_start_date")
    if end_date:
        lines.append(f"> Steady-state pricing begins: **{end_date}**.")
    grandfather = ls.get("grandfather_policy")
    if grandfather:
        lines.append(f"> Grandfather policy: {grandfather}")
    return "\n".join(lines)


def _render_competitors_block(competitors: List[Dict[str, Any]]) -> str:
    if not competitors:
        return "_No competitive anchors captured. That's a gap -- consider adding some before pricing decisions get locked into code._\n"
    lines = ["| Competitor | Monthly | Annual | Notes |", "|---|---|---|---|"]
    for c in competitors:
        monthly = _format_usd(c["monthly_price_usd"])
        annual = _format_usd(c["annual_price_usd"]) if c.get("annual_price_usd") else "--"
        notes = (c.get("notes") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {c['name']} | {monthly} | {annual} | {notes} |")
    return "\n".join(lines)


def _render_stripe_hints_block(version: Dict[str, Any]) -> str:
    """Concrete guidance for wiring Stripe -- one Product per tier, two Prices each."""
    lines = []
    for t in version["tiers"]:
        slug = re.sub(r"[^a-z0-9]+", "-", t["name"].lower()).strip("-")
        lines.append(f"- **`prod_{slug}`** -- {t['name']}")
        lines.append(f"  - `price_{slug}_monthly` -- {_format_usd(t['monthly_price_usd'])}/month")
        lines.append(f"  - `price_{slug}_annual` -- {_format_usd(t['annual_price_usd'])}/year")
        lines.append(f"  - metadata: `tier_name={t['name']}`, `target_segment={t['target_segment']}`")
    return "\n".join(lines)


def _render_version_history_block(sidecar: Dict[str, Any]) -> str:
    versions = sidecar["versions"]
    if len(versions) == 1:
        return "_This is version 1 -- no prior history yet._\n"
    lines = []
    for v in sorted(versions, key=lambda x: x["version"], reverse=True):
        marker = "**ACTIVE** " if v["version"] == sidecar["active_version"] else ""
        lines.append(f"### {marker}Version {v['version']} ({_human_date(v['created_at'])})")
        lines.append(f"_{v['rationale']}_")
        if v.get("active_until"):
            lines.append(f"Superseded {_human_date(v['active_until'])}.")
        lines.append("")
    return "\n".join(lines)


def _render_change_log_block(change_log: List[Dict[str, Any]]) -> str:
    if not change_log:
        return "_No iterations yet. Current version is the initial design._\n"
    lines = []
    for entry in change_log:
        lines.append(f"### {_human_date(entry['at'])} -- v{entry['from_version']} -> v{entry['to_version']}")
        lines.append(f"**Change**: {entry['change']}  \n**Reason**: {entry['reason']}\n")
    return "\n".join(lines)


def _annual_months_free(discount_pct: int) -> str:
    """Convert a discount percent into a readable 'X months free' equivalent."""
    months = round(12 * discount_pct / 100, 1)
    # Format nicely -- avoid '2.0', prefer '2'.
    return f"{months:g}"


def _render_markdown(sidecar: Dict[str, Any], profile: Dict[str, Any], output_dir: Path) -> Path:
    """Render PRICING.md from the sidecar. Returns the path written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    active = _active_version(sidecar)

    strategy_display = {
        "freemium": "Freemium",
        "free-trial": "Free Trial",
        "paid-only": "Paid Only",
    }.get(active["strategy"], active["strategy"])

    tmpl = PRICING_MD_TMPL.read_text(encoding="utf-8")
    substitutions = {
        "project_name": profile["project_name"],
        "project_slug": sidecar["project_slug"],
        "active_version": str(active["version"]),
        "updated_at_human": _human_date(sidecar["updated_at"]),
        "strategy_display": strategy_display,
        "offer_block": _render_offer_block(active),
        "tiers_block": _render_tiers_block(active),
        "trial_block": _render_trial_block(active),
        "billing_unit": active["billing_unit"],
        "value_metric": active["value_metric"],
        "annual_discount_percent": str(active["annual_discount_percent"]),
        "annual_months_free": _annual_months_free(active["annual_discount_percent"]),
        "launch_strategy_block": _render_launch_strategy_block(active),
        "competitors_block": _render_competitors_block(sidecar.get("competitors", [])),
        "stripe_hints_block": _render_stripe_hints_block(active),
        "version_history_block": _render_version_history_block(sidecar),
        "change_log_block": _render_change_log_block(sidecar.get("change_log", [])),
        "schema_version": str(sidecar["schema_version"]),
    }
    md = tmpl
    for k, v in substitutions.items():
        md = md.replace("{{" + k + "}}", v)

    out_path = output_dir / "PRICING.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path


def _resolve_output_dir(profile: Dict[str, Any], slug: str, override: Optional[str]) -> Path:
    """Same resolution rules as scope-guardian -- repo/docs if reachable, else staging."""
    if override:
        return Path(override).expanduser().resolve()
    repo_path = profile.get("repository_path")
    if repo_path:
        repo = Path(repo_path).expanduser()
        if repo.is_dir():
            return repo / "docs"
        _err(f"Repo path {repo} not reachable -- falling back to staging.")
    return PROFILES_DIR / f"{slug}_docs"


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_design(args: argparse.Namespace) -> int:
    """Create version 1 of the pricing sidecar from JSON on stdin.

    Expected stdin shape (minimum):
        {
          "competitors": [{"name":"X","monthly_price_usd":24}, ...],
          "version": { ...full pricing version object without 'version' or 'created_at'... }
        }
    """
    slug = args.slug
    profile = _load_profile(slug)

    # Business-model gate: pricing doesn't apply to some business models.
    bm = profile.get("business_model")
    if bm in ("free-self-hosted", "internal-only"):
        _err(f"business_model='{bm}' -- pricing not applicable to this project.")
        return 13

    if _pricing_path(slug).exists() and not args.force:
        _err(f"Pricing already designed for '{slug}'. Use `iterate` to add a new version, or pass --force to start over (destroys history).")
        return 7

    payload = _read_stdin_json()
    competitors = payload.get("competitors", [])
    if len(competitors) < 2 and not args.allow_thin_anchors:
        _err(f"Only {len(competitors)} competitor(s) supplied. Pricing without anchors is guessing.")
        _err("Add at least 2 competitor price points, or pass --allow-thin-anchors to override.")
        return 14

    version_in = payload.get("version")
    if not isinstance(version_in, dict):
        _err("Payload must include a 'version' object.")
        return 6

    now = _now_iso()

    # Stamp competitor capture dates if missing, so we know when each was recorded.
    for c in competitors:
        c.setdefault("captured_at", now[:10])

    # Assemble the full version record with managed fields.
    version = {
        "version": 1,
        "created_at": now,
        "active_until": None,
        **version_in,
    }

    sidecar = {
        "schema_version": 1,
        "project_slug": slug,
        "created_at": now,
        "updated_at": now,
        "active_version": 1,
        "competitors": competitors,
        "versions": [version],
        "change_log": [],
    }

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, _load_sidecar(slug))

    output_dir = _resolve_output_dir(profile, slug, None)
    md_path = _render_markdown(_load_sidecar(slug), profile, output_dir)

    print(f"Pricing sidecar : {_pricing_path(slug)}")
    print(f"PRICING.md      : {md_path}")
    print(f"Profile mirror  : profile.pricing_model (active_version=1)")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    sidecar = _load_sidecar(args.slug)
    if args.version is not None:
        selected = next((v for v in sidecar["versions"] if v["version"] == args.version), None)
        if selected is None:
            _err(f"No version {args.version} in sidecar.")
            return 11
    else:
        selected = _active_version(sidecar)

    if args.json:
        # When a specific version is requested, show just that. Otherwise show the whole sidecar.
        print(json.dumps(selected if args.version is not None else sidecar, indent=2))
        return 0

    profile = _load_profile(args.slug)
    is_active = selected["version"] == sidecar["active_version"]
    active_tag = " (ACTIVE)" if is_active else f" (superseded {_human_date(selected.get('active_until'))})"

    print(f"\n  {profile['project_name']}  ({args.slug})  --  Pricing v{selected['version']}{active_tag}")
    print(f"  Strategy     : {selected['strategy']}", end="")
    if selected.get("trial_days"):
        print(f"  ({selected['trial_days']}-day trial)")
    else:
        print()
    print(f"  Billing unit : {selected['billing_unit']}")
    print(f"  Value metric : {selected['value_metric']}")
    print(f"  Annual disc. : {selected['annual_discount_percent']}%")
    print(f"  Launch mode  : {selected.get('launch_strategy', {}).get('mode', '?')}")

    if selected.get("free_tier"):
        ft = selected["free_tier"]
        print(f"\n  FREE: {ft['name']}")
        if ft.get("tagline"):
            print(f"    {ft['tagline']}")

    print(f"\n  Paid tiers ({len(selected['tiers'])}):")
    for t in selected["tiers"]:
        flag = " ⭐" if t.get("highlighted") else ""
        print(f"    - {t['name']:<15}{flag:<3}  {_format_usd(t['monthly_price_usd'])}/mo  {_format_usd(t['annual_price_usd'])}/yr   [{t['target_segment']}]")

    print(f"\n  Competitors ({len(sidecar.get('competitors', []))}):")
    for c in sidecar.get("competitors", []):
        annual = _format_usd(c["annual_price_usd"]) if c.get("annual_price_usd") else "--"
        print(f"    - {c['name']:<20}  {_format_usd(c['monthly_price_usd'])}/mo  {annual}/yr")

    print(f"\n  Rationale: {selected['rationale']}")
    print()
    return 0


def cmd_iterate(args: argparse.Namespace) -> int:
    """Append a new version to the sidecar. Archives the previous one.

    Expected stdin shape:
        {
          "change": "what changed",
          "reason": "why",
          "version": { ...new pricing version... },
          "competitors_append": [{...}]    # optional -- add new competitive data
        }
    """
    slug = args.slug
    sidecar = _load_sidecar(slug)
    payload = _read_stdin_json()

    change = (payload.get("change") or "").strip()
    reason = (payload.get("reason") or "").strip()
    new_version_in = payload.get("version")
    if not change or not reason:
        _err("Iterate payload must include non-empty 'change' and 'reason'.")
        return 11
    if not isinstance(new_version_in, dict):
        _err("Iterate payload must include a 'version' object.")
        return 6

    now = _now_iso()
    prior_active = _active_version(sidecar)
    prior_active["active_until"] = now

    next_version_n = max(v["version"] for v in sidecar["versions"]) + 1
    new_version = {
        "version": next_version_n,
        "created_at": now,
        "active_until": None,
        **new_version_in,
    }

    sidecar["versions"].append(new_version)
    sidecar["active_version"] = next_version_n

    # Optional competitor append.
    for c in payload.get("competitors_append", []):
        c.setdefault("captured_at", now[:10])
        sidecar["competitors"].append(c)

    sidecar.setdefault("change_log", []).append({
        "at": now,
        "from_version": prior_active["version"],
        "to_version": next_version_n,
        "change": change,
        "reason": reason,
    })

    _write_sidecar(slug, sidecar)
    _mirror_to_profile(slug, _load_sidecar(slug))

    profile = _load_profile(slug)
    output_dir = _resolve_output_dir(profile, slug, None)
    md_path = _render_markdown(_load_sidecar(slug), profile, output_dir)

    print(f"New version     : v{next_version_n} (was v{prior_active['version']})")
    print(f"PRICING.md      : {md_path}")
    print(f"Profile mirror  : updated")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    sidecar = _load_sidecar(args.slug)
    profile = _load_profile(args.slug)
    output_dir = _resolve_output_dir(profile, args.slug, args.output_dir)
    path = _render_markdown(sidecar, profile, output_dir)
    print(f"Rendered: {path}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Remove sidecar + staged docs. Leaves profile.pricing_model in place --
    deleting pricing sessions shouldn't wipe data that Stripe code references."""
    path = _pricing_path(args.slug)
    if not path.exists():
        _err(f"No pricing sidecar for '{args.slug}'.")
        return 8
    if not args.yes:
        _err(f"Delete pricing for '{args.slug}'? Re-run with --yes to confirm.")
        _err("Note: profile.pricing_model is NOT cleared -- that would break Stripe code references.")
        return 9
    path.unlink()
    staged = PROFILES_DIR / f"{args.slug}_docs" / "PRICING.md"
    if staged.exists():
        staged.unlink()
    print(f"Deleted pricing for '{args.slug}' (profile.pricing_model retained).")
    return 0


# --------------------------------------------------------------------------- #
# Arg parsing                                                                 #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pricing_tool", description="SaaS Pricing Architect CRUD.")
    sub = p.add_subparsers(dest="command", required=True)

    p_design = sub.add_parser("design", help="Create version 1 from JSON on stdin.")
    p_design.add_argument("slug")
    p_design.add_argument("--from-stdin", action="store_true", required=True)
    p_design.add_argument("--force", action="store_true", help="Overwrite existing pricing (destroys history).")
    p_design.add_argument("--allow-thin-anchors", action="store_true",
                          help="Bypass the 2-competitor minimum. You shouldn't need this.")
    p_design.set_defaults(func=cmd_design)

    p_show = sub.add_parser("show", help="Display active or specific version.")
    p_show.add_argument("slug")
    p_show.add_argument("--version", type=int, help="Show a specific historical version instead of active.")
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_iterate = sub.add_parser("iterate", help="Append a new version (reads JSON on stdin).")
    p_iterate.add_argument("slug")
    p_iterate.add_argument("--from-stdin", action="store_true", required=True)
    p_iterate.set_defaults(func=cmd_iterate)

    p_render = sub.add_parser("render", help="Re-generate PRICING.md from the sidecar.")
    p_render.add_argument("slug")
    p_render.add_argument("--output-dir")
    p_render.set_defaults(func=cmd_render)

    p_delete = sub.add_parser("delete", help="Remove sidecar + rendered docs.")
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
