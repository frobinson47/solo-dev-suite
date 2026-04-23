#!/usr/bin/env python3
"""
testing_tool.py -- The workhorse for the testing-strategy skill.

Produces a right-sized, stack-aware testing strategy specifying what to
unit test / integration test / E2E test / manually test. Avoids both
under-testing and 100%-coverage dogma.

Commands:
    design   <slug> --from-stdin            # Initial strategy
    show     <slug> [--category <c>] [--json]
    iterate  <slug> --from-stdin            # Update (requires reason)
    review   <slug>                         # Mark as reviewed
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
SCHEMA_PATH = TEMPLATES_DIR / "testing.schema.json"
RENDER_TMPL = TEMPLATES_DIR / "TESTING_STRATEGY.md.tmpl"


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
    print(f"[testing_tool] {msg}", file=sys.stderr)


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


def _testing_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.testing.json"


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
# Sidecar helpers                                                             #
# --------------------------------------------------------------------------- #

def _load_sidecar(slug: str) -> Dict[str, Any]:
    data = _read_json(_testing_path(slug))
    if data is None:
        _err(f"No testing strategy sidecar for '{slug}'. Run 'design' first.")
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
    _write_json_atomic(_testing_path(slug), data)


# --------------------------------------------------------------------------- #
# Output directory + profile mirror                                           #
# --------------------------------------------------------------------------- #

def _resolve_output_dir(profile: Dict[str, Any], slug: str) -> Path:
    repo = profile.get("repository_path")
    if repo:
        repo_path = Path(repo)
        if repo_path.is_dir():
            return repo_path / "docs"
    return PROFILES_DIR / f"{slug}_docs"


def _mirror_to_profile(slug: str, sidecar: Dict[str, Any]) -> None:
    profile = _load_profile(slug)
    cats = sidecar["categories"]
    profile["testing_model"] = {
        "unit_coverage_target": cats["unit"]["coverage_target"],
        "integration_coverage_target": cats["integration"]["coverage_target"],
        "e2e_coverage_target": cats["e2e"]["coverage_target"],
        "tooling_unit": sidecar["tooling"]["unit_runner"],
        "last_strategy_review": sidecar["last_reviewed"],
    }
    if "last_skill_run" not in profile:
        profile["last_skill_run"] = {}
    profile["last_skill_run"]["testing-strategy"] = _now_iso()
    profile["updated_at"] = _now_iso()
    _write_json_atomic(_profile_path(slug), profile)


# --------------------------------------------------------------------------- #
# Staleness detection                                                         #
# --------------------------------------------------------------------------- #

_CADENCE_DAYS = {
    "monthly": 30,
    "quarterly": 90,
    "biannual": 180,
    "annual": 365,
}


def _is_stale(sidecar: Dict[str, Any]) -> bool:
    """Check if last_reviewed is older than the review_cadence."""
    last = sidecar.get("last_reviewed")
    if not last:
        return True
    try:
        reviewed = datetime.strptime(last[:19], "%Y-%m-%dT%H:%M:%S")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        days = (now - reviewed).days
        max_days = _CADENCE_DAYS.get(sidecar.get("review_cadence", "quarterly"), 90)
        return days > max_days
    except ValueError:
        return True


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_design(args: argparse.Namespace) -> None:
    slug = args.slug
    _ = _load_profile(slug)

    existing = _read_json(_testing_path(slug))
    if existing is not None:
        _err(f"Testing strategy already exists for '{slug}'. Use 'iterate' to update.")
        sys.exit(7)

    payload = _read_stdin_json()

    # Validate required top-level fields
    required = ["tooling", "categories", "ci", "review_cadence", "rationale"]
    missing = [f for f in required if f not in payload]
    if missing:
        _err(f"Missing required fields: {', '.join(missing)}")
        sys.exit(6)

    # Validate categories have all 4
    cats = payload.get("categories", {})
    for cat_name in ["unit", "integration", "e2e", "manual"]:
        if cat_name not in cats:
            _err(f"Missing category: {cat_name}")
            sys.exit(6)

    now = _now_iso()
    sidecar = {
        "schema_version": 1,
        "project_slug": slug,
        "created_at": now,
        "updated_at": now,
        "tooling": payload["tooling"],
        "categories": payload["categories"],
        "ci": payload["ci"],
        "review_cadence": payload["review_cadence"],
        "last_reviewed": now,
        "rationale": payload["rationale"],
        "history": [
            {"at": now, "action": "designed", "reason": "Initial testing strategy"}
        ],
    }

    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    # Summary
    total_effort = sum(cats[c].get("effort_ratio_percent", 0) for c in ["unit", "integration", "e2e", "manual"])
    total_targets = sum(len(cats[c].get("targets", [])) for c in ["unit", "integration", "e2e", "manual"])
    total_skips = sum(len(cats[c].get("explicitly_skip", [])) for c in ["unit", "integration", "e2e", "manual"])

    print(f"Testing strategy designed for '{slug}'.")
    print(f"  Tooling: {payload['tooling']['unit_runner']} (unit), {payload['tooling']['e2e_runner']} (e2e)")
    print(f"  Effort split: unit={cats['unit']['effort_ratio_percent']}% integration={cats['integration']['effort_ratio_percent']}% e2e={cats['e2e']['effort_ratio_percent']}% manual={cats['manual']['effort_ratio_percent']}%")
    print(f"  Total targets: {total_targets} | Explicit skips: {total_skips}")
    print(f"  Review cadence: {payload['review_cadence']}")


def cmd_show(args: argparse.Namespace) -> None:
    slug = args.slug
    sidecar = _load_sidecar(slug)

    if getattr(args, 'json', False):
        print(json.dumps(sidecar, indent=2))
        return

    cat_filter = getattr(args, 'category', None)
    cats = sidecar["categories"]

    # Staleness check
    stale = _is_stale(sidecar)

    print(f"=== Testing Strategy: {slug} ===")
    if stale:
        print(f"  ** STALE ** -- last reviewed {_human_date(sidecar['last_reviewed'])}, cadence is {sidecar['review_cadence']}")
    else:
        print(f"  Last reviewed: {_human_date(sidecar['last_reviewed'])} (cadence: {sidecar['review_cadence']})")

    print(f"  Tooling: {sidecar['tooling']['unit_runner']} / {sidecar['tooling']['integration_runner']} / {sidecar['tooling']['e2e_runner']}")
    print()

    show_cats = [cat_filter] if cat_filter and cat_filter in cats else ["unit", "integration", "e2e", "manual"]

    for cat_name in show_cats:
        cat = cats[cat_name]
        print(f"  [{cat_name.upper()}] coverage={cat['coverage_target']} effort={cat['effort_ratio_percent']}%")
        for t in cat.get("targets", []):
            print(f"    + {t['area']} -- {t['why']}")
        for s in cat.get("explicitly_skip", []):
            print(f"    - SKIP {s['area']} -- {s['why']}")
        if cat.get("fixtures_strategy"):
            print(f"    Fixtures: {cat['fixtures_strategy']}")
        print()

    # CI gates
    gates = sidecar["ci"]["gates"]
    gate_parts = []
    if gates["unit_must_pass"]:
        gate_parts.append("unit")
    if gates["integration_must_pass"]:
        gate_parts.append("integration")
    if gates["e2e_must_pass"]:
        gate_parts.append("e2e")
    print(f"  CI gates: {', '.join(gate_parts) if gate_parts else 'none'}")
    print(f"  CI runs on: {', '.join(sidecar['ci']['runs_on'])}")


def cmd_iterate(args: argparse.Namespace) -> None:
    slug = args.slug
    sidecar = _load_sidecar(slug)

    payload = _read_stdin_json()

    reason = payload.get("reason", "")
    if not reason:
        _err("Iteration requires a 'reason' field explaining what changed and why.")
        sys.exit(11)

    # Merge provided fields
    updated_fields = []
    if "tooling" in payload:
        sidecar["tooling"] = payload["tooling"]
        updated_fields.append("tooling")
    if "categories" in payload:
        # Merge per-category
        for cat_name in ["unit", "integration", "e2e", "manual"]:
            if cat_name in payload["categories"]:
                sidecar["categories"][cat_name] = payload["categories"][cat_name]
                updated_fields.append(f"categories.{cat_name}")
    if "ci" in payload:
        sidecar["ci"] = payload["ci"]
        updated_fields.append("ci")
    if "review_cadence" in payload:
        sidecar["review_cadence"] = payload["review_cadence"]
        updated_fields.append("review_cadence")
    if "rationale" in payload:
        sidecar["rationale"] = payload["rationale"]
        updated_fields.append("rationale")

    if not updated_fields:
        _err("No updatable fields provided (tooling, categories, ci, review_cadence, rationale).")
        sys.exit(6)

    sidecar["history"].append({
        "at": _now_iso(),
        "action": "iterated",
        "reason": reason,
    })

    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    print(f"Testing strategy updated for '{slug}'.")
    print(f"  Changed: {', '.join(updated_fields)}")
    print(f"  Reason: {reason}")


def cmd_review(args: argparse.Namespace) -> None:
    slug = args.slug
    sidecar = _load_sidecar(slug)

    now = _now_iso()
    sidecar["last_reviewed"] = now
    sidecar["history"].append({
        "at": now,
        "action": "reviewed",
        "reason": "Periodic review",
    })

    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    print(f"Testing strategy reviewed for '{slug}'.")
    print(f"  Next review due: {sidecar['review_cadence']}")


def cmd_render(args: argparse.Namespace) -> None:
    slug = args.slug
    profile = _load_profile(slug)
    sidecar = _load_sidecar(slug)

    output_dir = Path(args.output_dir) if getattr(args, 'output_dir', None) else _resolve_output_dir(profile, slug)
    cats = sidecar["categories"]
    tooling = sidecar["tooling"]

    def _esc(s: str) -> str:
        return s.replace('|', '\\|')

    # Effort chart (ASCII bar)
    effort_lines = []
    for cat_name in ["unit", "integration", "e2e", "manual"]:
        pct = cats[cat_name]["effort_ratio_percent"]
        bar = "#" * (pct // 2)
        effort_lines.append(f"| {cat_name.capitalize():13} | {pct:3d}% | {bar} |")
    effort_chart = "| Category      |  %  | Distribution |\n|---------------|-----|--------------|\n" + "\n".join(effort_lines)

    def _targets_block(cat: Dict[str, Any]) -> str:
        targets = cat.get("targets", [])
        if not targets:
            return "_No specific targets defined._"
        lines = ["| Area | Why |", "|------|-----|"]
        for t in targets:
            lines.append(f"| {_esc(t['area'])} | {_esc(t['why'])} |")
        return "\n".join(lines)

    def _skip_block(cat: Dict[str, Any]) -> str:
        skips = cat.get("explicitly_skip", [])
        if not skips:
            return "_Nothing explicitly skipped._"
        lines = ["| Area | Why Skip |", "|------|----------|"]
        for s in skips:
            lines.append(f"| {_esc(s['area'])} | {_esc(s['why'])} |")
        return "\n".join(lines)

    # CI block
    ci = sidecar["ci"]
    ci_lines = [f"**Runs on:** {', '.join(ci['runs_on'])}", ""]
    ci_lines.append("| Gate | Required |")
    ci_lines.append("|------|----------|")
    ci_lines.append(f"| Unit tests pass | {'Yes' if ci['gates']['unit_must_pass'] else 'No'} |")
    ci_lines.append(f"| Integration tests pass | {'Yes' if ci['gates']['integration_must_pass'] else 'No'} |")
    ci_lines.append(f"| E2E tests pass | {'Yes' if ci['gates']['e2e_must_pass'] else 'No'} |")
    threshold = ci['gates']['coverage_threshold_percent']
    ci_lines.append(f"| Coverage threshold | {str(threshold) + '%' if threshold is not None else 'None'} |")
    ci_block = "\n".join(ci_lines)

    # Review block
    stale = _is_stale(sidecar)
    review_status = "**STALE -- review overdue**" if stale else "Current"
    review_block = f"**Cadence:** {sidecar['review_cadence']} | **Last reviewed:** {_human_date(sidecar['last_reviewed'])} | **Status:** {review_status}"

    # History block
    history = sidecar.get("history", [])[-20:]
    if history:
        h_lines = ["| Date | Action | Reason |", "|------|--------|--------|"]
        for entry in reversed(history):
            h_lines.append(f"| {_human_date(entry['at'])} | {entry['action']} | {_esc(entry['reason'])} |")
        history_block = "\n".join(h_lines)
    else:
        history_block = "_No history._"

    # Render template
    tmpl = RENDER_TMPL.read_text(encoding="utf-8")
    project_name = profile.get("project_name", slug)

    result = tmpl
    result = result.replace("{{project_name}}", _esc(project_name))
    result = result.replace("{{project_slug}}", slug)
    result = result.replace("{{unit_runner}}", _esc(tooling["unit_runner"]))
    result = result.replace("{{integration_runner}}", _esc(tooling["integration_runner"]))
    result = result.replace("{{e2e_runner}}", _esc(tooling["e2e_runner"]))
    result = result.replace("{{coverage_tool}}", _esc(tooling["coverage_tool"]))
    result = result.replace("{{effort_chart}}", effort_chart)

    for cat_name in ["unit", "integration", "e2e", "manual"]:
        cat = cats[cat_name]
        result = result.replace(f"{{{{{cat_name}_target}}}}", cat["coverage_target"])
        result = result.replace(f"{{{{{cat_name}_effort}}}}", str(cat["effort_ratio_percent"]))
        result = result.replace(f"{{{{{cat_name}_targets_block}}}}", _targets_block(cat))
        result = result.replace(f"{{{{{cat_name}_skip_block}}}}", _skip_block(cat))
        result = result.replace(f"{{{{{cat_name}_fixtures}}}}", _esc(cat.get("fixtures_strategy", "")))

    result = result.replace("{{ci_block}}", ci_block)
    result = result.replace("{{review_block}}", review_block)
    result = result.replace("{{rationale}}", _esc(sidecar["rationale"]))
    result = result.replace("{{history_block}}", history_block)

    out_path = output_dir / "TESTING_STRATEGY.md"
    _write_text_atomic(out_path, result)
    print(f"Rendered: {out_path}")


def cmd_delete(args: argparse.Namespace) -> None:
    slug = args.slug
    path = _testing_path(slug)

    if not path.exists():
        _err(f"No testing strategy sidecar for '{slug}'.")
        sys.exit(10)

    if not getattr(args, 'yes', False):
        _err(f"This will delete the testing strategy for '{slug}'. Pass --yes to confirm.")
        sys.exit(9)

    path.unlink()
    print(f"Testing strategy sidecar deleted for '{slug}'.")


# --------------------------------------------------------------------------- #
# CLI wiring                                                                  #
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="testing_tool.py",
        description="Testing Strategy: design and maintain a right-sized test plan."
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    # design
    p_design = sub.add_parser("design", help="Create initial testing strategy from stdin")
    p_design.add_argument("slug")
    p_design.add_argument("--from-stdin", action="store_true", default=True)

    # show
    p_show = sub.add_parser("show", help="Display testing strategy")
    p_show.add_argument("slug")
    p_show.add_argument("--category", choices=["unit", "integration", "e2e", "manual"])
    p_show.add_argument("--json", action="store_true")

    # iterate
    p_iter = sub.add_parser("iterate", help="Update strategy (requires reason)")
    p_iter.add_argument("slug")
    p_iter.add_argument("--from-stdin", action="store_true", default=True)

    # review
    p_review = sub.add_parser("review", help="Mark strategy as reviewed")
    p_review.add_argument("slug")

    # render
    p_render = sub.add_parser("render", help="Generate TESTING_STRATEGY.md")
    p_render.add_argument("slug")
    p_render.add_argument("--output-dir")

    # delete
    p_del = sub.add_parser("delete", help="Delete the sidecar")
    p_del.add_argument("slug")
    p_del.add_argument("--yes", action="store_true")

    args = parser.parse_args()

    commands = {
        "design": cmd_design,
        "show": cmd_show,
        "iterate": cmd_iterate,
        "review": cmd_review,
        "render": cmd_render,
        "delete": cmd_delete,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
