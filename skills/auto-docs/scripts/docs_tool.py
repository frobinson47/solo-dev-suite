#!/usr/bin/env python3
"""
docs_tool.py -- The workhorse for the auto-docs skill.

Generates and maintains baseline project documentation (README.md, SETUP.md,
ARCHITECTURE.md, CHANGELOG.md) by pulling from the profile and sibling sidecars.
Re-runnable at every milestone so docs stay current without being a full-time job.

Commands:
    init            <slug> --from-stdin   # Create sidecar with user_content
    generate        <slug> [--only <doc>] # Regenerate one or all docs
    release         <slug> --from-stdin   # Append a release, regenerate CHANGELOG + README
    update-content  <slug> --from-stdin   # Modify user_content fields
    show            <slug> [--json]       # Display current sidecar state
    delete          <slug> [--yes]        # Remove sidecar, NOT generated .md files

Design notes:
  * Templates use {{key}} substitution, no Jinja.
  * Preserved regions (HTML comment markers) survive regeneration.
  * Each doc conditionally includes sections based on which sidecars exist.
  * Releases are append-only -- no editing past releases.
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

SCRIPT_DIR = Path(__file__).resolve().parent       # .../auto-docs/scripts
SKILL_DIR = SCRIPT_DIR.parent                       # .../auto-docs
TEMPLATES_DIR = SKILL_DIR / "templates"
SCHEMA_PATH = TEMPLATES_DIR / "docs.schema.json"


def _find_suite_dir() -> Path:
    """Locate solo-dev-suite as a sibling of this skill's directory."""
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
    print(f"[docs_tool] {msg}", file=sys.stderr)


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


def _docs_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.docs.json"


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
# Output directory resolution                                                 #
# --------------------------------------------------------------------------- #

def _resolve_output_dir(profile: Dict[str, Any], slug: str) -> Tuple[Path, Path]:
    """Returns (root_dir, docs_dir) for generated files.

    README.md goes in root_dir. SETUP.md, ARCHITECTURE.md, CHANGELOG.md go
    in docs_dir (root_dir/docs/).

    If the profile has a reachable repository_path, use that.
    Otherwise fall back to profiles/<slug>_docs/ as staging.
    """
    repo = profile.get("repository_path")
    if repo:
        repo_path = Path(repo)
        if repo_path.is_dir():
            docs_dir = repo_path / "docs"
            return repo_path, docs_dir

    # Fallback staging location
    staging = PROFILES_DIR / f"{slug}_docs"
    return staging, staging / "docs"


# --------------------------------------------------------------------------- #
# Preserved region handling                                                   #
# --------------------------------------------------------------------------- #

_PRESERVED_RE = re.compile(
    r'<!-- auto-docs:preserved:start -->\n(.*?)<!-- auto-docs:preserved:end -->',
    re.DOTALL
)

_AUTO_DOCS_MARKER = '<!-- auto-docs:'


def _extract_preserved(text: str) -> List[str]:
    """Pull all preserved regions from an existing generated file."""
    return _PRESERVED_RE.findall(text)


def _has_auto_docs_markers(text: str) -> bool:
    """Check if a file was generated by auto-docs (has our marker comments)."""
    return _AUTO_DOCS_MARKER in text


def _stitch_preserved(new_text: str, preserved: List[str]) -> str:
    """Re-insert preserved regions into newly generated text.

    Each <!-- auto-docs:preserved:start/end --> pair in the new text gets
    its content replaced with the corresponding preserved region from the
    old file, in order.
    """
    if not preserved:
        return new_text

    idx = 0

    def replacer(match: re.Match) -> str:
        nonlocal idx
        if idx < len(preserved):
            content = preserved[idx]
            idx += 1
            return f"<!-- auto-docs:preserved:start -->\n{content}<!-- auto-docs:preserved:end -->"
        return match.group(0)

    return _PRESERVED_RE.sub(replacer, new_text)


# --------------------------------------------------------------------------- #
# Sidecar helpers                                                             #
# --------------------------------------------------------------------------- #

def _load_sidecar(slug: str) -> Dict[str, Any]:
    """Load the docs sidecar, exit if missing."""
    path = _docs_path(slug)
    data = _read_json(path)
    if data is None:
        _err(f"No docs sidecar for '{slug}'. Run 'init' first.")
        sys.exit(10)
    return data


def _load_profile(slug: str) -> Dict[str, Any]:
    """Load the project profile, exit if missing."""
    path = _profile_path(slug)
    data = _read_json(path)
    if data is None:
        _err(f"No profile for '{slug}'. Onboard the project first.")
        sys.exit(2)
    return data


def _save_sidecar(slug: str, data: Dict[str, Any]) -> None:
    """Validate and atomically write the sidecar."""
    data["updated_at"] = _now_iso()
    errors = _validate_sidecar(data)
    if errors:
        _err(f"Sidecar validation failed:\n  " + "\n  ".join(errors))
        sys.exit(4)
    _write_json_atomic(_docs_path(slug), data)


# --------------------------------------------------------------------------- #
# Profile mirror + last_skill_run                                             #
# --------------------------------------------------------------------------- #

def _mirror_to_profile(slug: str, sidecar: Dict[str, Any]) -> None:
    """Write lean docs_model summary to profile + update last_skill_run."""
    profile = _load_profile(slug)

    latest_release = None
    if sidecar["releases"]:
        latest_release = sidecar["releases"][-1]["version"]

    generated_docs = []
    gen = sidecar["generated_sections"]
    if gen["last_generated_at"]:
        # Figure out which docs exist by checking sources
        generated_docs = ["README.md", "SETUP.md", "CHANGELOG.md", "ARCHITECTURE.md"]

    profile["docs_model"] = {
        "last_generated_at": gen["last_generated_at"],
        "generated_docs": generated_docs,
        "latest_release": latest_release,
    }

    if "last_skill_run" not in profile:
        profile["last_skill_run"] = {}
    profile["last_skill_run"]["auto-docs"] = _now_iso()
    profile["updated_at"] = _now_iso()
    _write_json_atomic(_profile_path(slug), profile)


# --------------------------------------------------------------------------- #
# Document generation logic                                                   #
# --------------------------------------------------------------------------- #

def _esc_table(s: str) -> str:
    """Escape pipe chars for Markdown tables."""
    return s.replace('|', '\\|')


def _detect_sources(slug: str) -> Dict[str, bool]:
    """Check which sibling sidecars exist for this project."""
    return {
        "profile": _profile_path(slug).exists(),
        "scope": (PROFILES_DIR / f"{slug}.scope.json").exists(),
        "pricing": (PROFILES_DIR / f"{slug}.pricing.json").exists(),
        "adrs": (PROFILES_DIR / f"{slug}.adr.json").exists(),
        "integrations": (PROFILES_DIR / f"{slug}.integrations.json").exists(),
        "security": (PROFILES_DIR / f"{slug}.security.json").exists(),
    }


def _generate_readme(profile: Dict[str, Any], sidecar: Dict[str, Any], slug: str) -> str:
    """Generate README.md content from profile + sidecar."""
    uc = sidecar["user_content"]
    tmpl = (TEMPLATES_DIR / "README.md.tmpl").read_text(encoding="utf-8")

    # Stack summary: comma-separated list
    stack = profile.get("primary_stack") or []
    stack_summary = ", ".join(stack) if stack else "(not specified)"

    # Pricing block -- only if profile has pricing_model
    pricing_block = ""
    pm = profile.get("pricing_model")
    if pm and isinstance(pm, dict):
        strategy = pm.get("strategy", "")
        pricing_block = (
            "<!-- auto-docs:start:pricing -->\n"
            "## Pricing\n\n"
            f"Strategy: **{_esc_table(strategy)}**\n\n"
            "See [PRICING.md](docs/PRICING.md) for full tier details.\n"
            "<!-- auto-docs:end:pricing -->"
        )

    # Latest release block
    latest_release_block = ""
    if sidecar["releases"]:
        rel = sidecar["releases"][-1]
        lines = [
            "<!-- auto-docs:start:release -->",
            "## Latest Release",
            "",
            f"**{_esc_table(rel['version'])}** -- {_esc_table(rel['headline'])}",
            "",
        ]
        if rel.get("highlights"):
            for h in rel["highlights"]:
                lines.append(f"- {_esc_table(h)}")
            lines.append("")
        lines.append("See [CHANGELOG.md](docs/CHANGELOG.md) for full history.")
        lines.append("<!-- auto-docs:end:release -->")
        latest_release_block = "\n".join(lines)

    # Screenshots block
    screenshots_block = ""
    if uc.get("screenshots"):
        lines = ["<!-- auto-docs:start:screenshots -->", "## Screenshots", ""]
        for ss in uc["screenshots"]:
            lines.append(f"![{_esc_table(ss['caption'])}]({ss['path']})")
            lines.append("")
        lines.append("<!-- auto-docs:end:screenshots -->")
        screenshots_block = "\n".join(lines)

    # Contact block
    contact_block = ""
    if uc.get("support_contact"):
        contact_block = (
            "<!-- auto-docs:start:contact -->\n"
            "## Contact\n\n"
            f"{_esc_table(uc['support_contact'])}\n"
            "<!-- auto-docs:end:contact -->"
        )

    result = tmpl
    result = result.replace("{{project_name}}", _esc_table(profile.get("project_name", slug)))
    result = result.replace("{{headline}}", _esc_table(uc.get("headline", "")))
    result = result.replace("{{status_badge}}", uc.get("status_badge", "in-development"))
    result = result.replace("{{current_phase}}", profile.get("current_phase", "(unknown)"))
    result = result.replace("{{launch_target_date}}", profile.get("launch_target_date", "(not set)"))
    result = result.replace("{{stack_summary}}", _esc_table(stack_summary))
    result = result.replace("{{description}}", _esc_table(profile.get("description", "(no description)")))
    result = result.replace("{{target_users}}", _esc_table(profile.get("target_users", "(not specified)")))
    result = result.replace("{{pricing_block}}", pricing_block)
    result = result.replace("{{latest_release_block}}", latest_release_block)
    result = result.replace("{{screenshots_block}}", screenshots_block)
    result = result.replace("{{contact_block}}", contact_block)
    result = result.replace("{{project_slug}}", slug)

    return result


def _generate_setup(profile: Dict[str, Any], sidecar: Dict[str, Any], slug: str) -> str:
    """Generate SETUP.md content."""
    uc = sidecar["user_content"]
    tmpl = (TEMPLATES_DIR / "SETUP.md.tmpl").read_text(encoding="utf-8")

    # Stack block
    stack = profile.get("primary_stack") or []
    if stack:
        stack_lines = []
        for item in stack:
            stack_lines.append(f"- {_esc_table(item)}")
        stack_block = "\n".join(stack_lines)
    else:
        stack_block = "(no stack defined in profile)"

    # Install steps block
    steps = uc.get("install_steps") or []
    if steps:
        install_lines = []
        for i, step in enumerate(steps, 1):
            install_lines.append(f"{i}. {_esc_table(step)}")
        install_steps_block = "\n".join(install_lines)
    else:
        install_steps_block = "(no install steps defined -- run `update-content` to add them)"

    # Hosting block
    hosting_block = ""
    hosting = profile.get("hosting")
    if hosting:
        hosting_block = (
            "<!-- auto-docs:start:hosting -->\n"
            "## Hosting\n\n"
            f"{_esc_table(hosting)}\n"
            "<!-- auto-docs:end:hosting -->"
        )

    result = tmpl
    result = result.replace("{{project_name}}", _esc_table(profile.get("project_name", slug)))
    result = result.replace("{{stack_block}}", stack_block)
    result = result.replace("{{install_steps_block}}", install_steps_block)
    result = result.replace("{{hosting_block}}", hosting_block)
    result = result.replace("{{project_slug}}", slug)

    return result


def _generate_architecture(profile: Dict[str, Any], sidecar: Dict[str, Any], slug: str) -> str:
    """Generate ARCHITECTURE.md content."""
    tmpl = (TEMPLATES_DIR / "ARCHITECTURE.md.tmpl").read_text(encoding="utf-8")

    # Stack table
    stack = profile.get("primary_stack") or []
    if stack:
        lines = ["| Technology | Role |", "|------------|------|"]
        for item in stack:
            lines.append(f"| {_esc_table(item)} | -- |")
        stack_table = "\n".join(lines)
    else:
        stack_table = "(no stack defined in profile)"

    # Third-party services block
    services_block = ""
    services = profile.get("third_party_services") or []
    if services:
        svc_lines = [
            "<!-- auto-docs:start:services -->",
            "## Third-Party Services",
            "",
            "| Service | Purpose | Risk |",
            "|---------|---------|------|",
        ]
        for svc in services:
            name = _esc_table(svc.get("name", "?"))
            purpose = _esc_table(svc.get("purpose", ""))
            risk = _esc_table(svc.get("risk_level", ""))
            svc_lines.append(f"| {name} | {purpose} | {risk} |")
        svc_lines.append("")
        svc_lines.append("See [INTEGRATIONS.md](INTEGRATIONS.md) for full risk analysis.")
        svc_lines.append("<!-- auto-docs:end:services -->")
        services_block = "\n".join(svc_lines)

    # ADRs block
    adrs_block = ""
    adr_model = profile.get("adr_model")
    if adr_model and isinstance(adr_model, dict) and adr_model.get("total_adrs", 0) > 0:
        adrs_block = (
            "<!-- auto-docs:start:adrs -->\n"
            "## Architecture Decision Records\n\n"
            f"**{adr_model['total_adrs']}** ADRs recorded"
            f" ({adr_model.get('accepted', 0)} accepted,"
            f" {adr_model.get('proposed', 0)} proposed,"
            f" {adr_model.get('superseded', 0)} superseded,"
            f" {adr_model.get('deprecated', 0)} deprecated).\n\n"
            "See [docs/adr/](adr/) for the full record.\n"
            "<!-- auto-docs:end:adrs -->"
        )

    # Hosting block
    hosting_block = ""
    hosting = profile.get("hosting")
    if hosting:
        hosting_block = (
            "<!-- auto-docs:start:hosting -->\n"
            "## Hosting & Deployment\n\n"
            f"{_esc_table(hosting)}\n"
            "<!-- auto-docs:end:hosting -->"
        )

    result = tmpl
    result = result.replace("{{project_name}}", _esc_table(profile.get("project_name", slug)))
    result = result.replace("{{stack_table}}", stack_table)
    result = result.replace("{{services_block}}", services_block)
    result = result.replace("{{adrs_block}}", adrs_block)
    result = result.replace("{{hosting_block}}", hosting_block)
    result = result.replace("{{project_slug}}", slug)

    return result


def _generate_changelog(profile: Dict[str, Any], sidecar: Dict[str, Any], slug: str) -> str:
    """Generate CHANGELOG.md content."""
    tmpl = (TEMPLATES_DIR / "CHANGELOG.md.tmpl").read_text(encoding="utf-8")

    releases = sidecar.get("releases") or []
    if not releases:
        releases_block = "_No releases yet._"
    else:
        lines = []
        # Newest first
        for rel in reversed(releases):
            lines.append(f"## {_esc_table(rel['version'])} -- {_esc_table(rel['headline'])}")
            lines.append("")
            lines.append(f"_Released: {_human_date(rel.get('released_at'))}_")
            lines.append("")

            if rel.get("breaking"):
                lines.append("### Breaking Changes")
                lines.append("")
                for b in rel["breaking"]:
                    lines.append(f"- {_esc_table(b)}")
                lines.append("")

            if rel.get("highlights"):
                lines.append("### Highlights")
                lines.append("")
                for h in rel["highlights"]:
                    lines.append(f"- {_esc_table(h)}")
                lines.append("")

            if rel.get("fixes"):
                lines.append("### Fixes")
                lines.append("")
                for f in rel["fixes"]:
                    lines.append(f"- {_esc_table(f)}")
                lines.append("")

            lines.append("---")
            lines.append("")

        releases_block = "\n".join(lines)

    result = tmpl
    result = result.replace("{{project_name}}", _esc_table(profile.get("project_name", slug)))
    result = result.replace("{{releases_block}}", releases_block)
    result = result.replace("{{project_slug}}", slug)

    return result


# Map of doc name -> (generator function, filename, goes_in_docs_subdir)
_DOC_MAP = {
    "README": (_generate_readme, "README.md", False),
    "SETUP": (_generate_setup, "SETUP.md", True),
    "ARCHITECTURE": (_generate_architecture, "ARCHITECTURE.md", True),
    "CHANGELOG": (_generate_changelog, "CHANGELOG.md", True),
}


def _write_doc(root_dir: Path, docs_dir: Path, doc_name: str,
               generator, filename: str, in_docs: bool,
               profile: Dict[str, Any], sidecar: Dict[str, Any], slug: str,
               force: bool = False) -> Path:
    """Generate and write a single doc, preserving user content."""
    target_dir = docs_dir if in_docs else root_dir
    target_path = target_dir / filename

    # Check for existing file without auto-docs markers
    preserved = []
    if target_path.exists():
        existing = target_path.read_text(encoding="utf-8")
        if not _has_auto_docs_markers(existing) and not force:
            _err(
                f"{target_path} exists but was not generated by auto-docs. "
                f"Use --force to overwrite, or add auto-docs markers manually."
            )
            return target_path
        # Extract preserved regions from existing file
        preserved = _extract_preserved(existing)

    # Generate new content
    new_content = generator(profile, sidecar, slug)

    # Stitch preserved regions back in
    if preserved:
        new_content = _stitch_preserved(new_content, preserved)

    _write_text_atomic(target_path, new_content)
    return target_path


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_init(args: argparse.Namespace) -> None:
    slug = args.slug
    profile = _load_profile(slug)

    existing = _read_json(_docs_path(slug))
    if existing is not None:
        _err(f"Docs sidecar already exists for '{slug}'. Use 'update-content' to modify.")
        sys.exit(7)

    payload = _read_stdin_json()

    # Validate required user_content fields
    required_fields = ["headline", "status_badge", "install_steps", "support_contact"]
    missing = [f for f in required_fields if f not in payload]
    if missing:
        _err(f"Missing required fields: {', '.join(missing)}")
        sys.exit(6)

    # Validate status_badge
    valid_badges = ["in-development", "alpha", "beta", "production", "maintenance"]
    if payload.get("status_badge") not in valid_badges:
        _err(f"status_badge must be one of: {', '.join(valid_badges)}")
        sys.exit(6)

    now = _now_iso()
    sidecar = {
        "schema_version": 1,
        "project_slug": slug,
        "created_at": now,
        "updated_at": now,
        "user_content": {
            "headline": payload["headline"],
            "status_badge": payload["status_badge"],
            "install_steps": payload.get("install_steps", []),
            "screenshots": payload.get("screenshots", []),
            "support_contact": payload.get("support_contact", ""),
        },
        "releases": [],
        "generated_sections": {
            "last_generated_at": None,
            "sources": {
                "profile": False,
                "scope": False,
                "pricing": False,
                "adrs": False,
                "integrations": False,
                "security": False,
            },
        },
    }

    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    # Check for phase/badge mismatch
    phase = profile.get("current_phase", "")
    badge = sidecar["user_content"]["status_badge"]
    if phase in ("ship", "grow", "sustain") and badge == "in-development":
        _err(f"Warning: profile phase is '{phase}' but status_badge is 'in-development'. Consider updating.")

    print(f"Docs sidecar created for '{slug}'.")
    print(f"  Headline: {sidecar['user_content']['headline']}")
    print(f"  Status: {sidecar['user_content']['status_badge']}")
    print(f"  Install steps: {len(sidecar['user_content']['install_steps'])}")
    print(f"Run 'generate {slug}' to produce the doc files.")


def cmd_generate(args: argparse.Namespace) -> None:
    slug = args.slug
    profile = _load_profile(slug)
    sidecar = _load_sidecar(slug)
    force = getattr(args, 'force', False)

    root_dir, docs_dir = _resolve_output_dir(profile, slug)

    # Determine which docs to generate
    only = getattr(args, 'only', None)
    if only:
        only_upper = only.upper().replace(".MD", "")
        if only_upper not in _DOC_MAP:
            _err(f"Unknown doc '{only}'. Valid: {', '.join(_DOC_MAP.keys())}")
            sys.exit(6)
        targets = {only_upper: _DOC_MAP[only_upper]}
    else:
        targets = _DOC_MAP

    # Detect sources
    sources = _detect_sources(slug)

    # Generate each doc
    written = []
    for doc_name, (generator, filename, in_docs) in targets.items():
        path = _write_doc(root_dir, docs_dir, doc_name, generator, filename,
                          in_docs, profile, sidecar, slug, force)
        written.append(str(path))
        print(f"  Generated: {path}")

    # Update sidecar metadata
    sidecar["generated_sections"]["last_generated_at"] = _now_iso()
    sidecar["generated_sections"]["sources"] = sources
    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    print(f"\n{len(written)} doc(s) generated for '{slug}'.")
    output_label = str(root_dir)
    print(f"Output: {output_label}")


def cmd_release(args: argparse.Namespace) -> None:
    slug = args.slug
    profile = _load_profile(slug)
    sidecar = _load_sidecar(slug)

    payload = _read_stdin_json()

    required = ["version", "headline"]
    missing = [f for f in required if f not in payload]
    if missing:
        _err(f"Missing required fields: {', '.join(missing)}")
        sys.exit(6)

    # Check for duplicate version
    existing_versions = [r["version"] for r in sidecar["releases"]]
    if payload["version"] in existing_versions:
        _err(f"Version '{payload['version']}' already exists. Releases are append-only.")
        sys.exit(7)

    release = {
        "version": payload["version"],
        "released_at": _now_iso(),
        "headline": payload["headline"],
        "highlights": payload.get("highlights", []),
        "fixes": payload.get("fixes", []),
        "breaking": payload.get("breaking", []),
    }

    sidecar["releases"].append(release)
    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    print(f"Release {release['version']} appended for '{slug}'.")
    print(f"  Headline: {release['headline']}")
    print(f"  Highlights: {len(release['highlights'])}")
    print(f"  Fixes: {len(release['fixes'])}")
    print(f"  Breaking: {len(release['breaking'])}")
    print(f"Run 'generate {slug}' to update CHANGELOG.md and README.md.")


def cmd_update_content(args: argparse.Namespace) -> None:
    slug = args.slug
    sidecar = _load_sidecar(slug)

    payload = _read_stdin_json()

    # Merge into user_content -- only update fields that are provided
    uc = sidecar["user_content"]
    valid_fields = ["headline", "status_badge", "install_steps", "screenshots", "support_contact"]

    updated = []
    for field in valid_fields:
        if field in payload:
            uc[field] = payload[field]
            updated.append(field)

    if not updated:
        _err("No valid fields provided. Valid: " + ", ".join(valid_fields))
        sys.exit(6)

    _save_sidecar(slug, sidecar)
    _mirror_to_profile(slug, sidecar)

    print(f"Updated user_content for '{slug}': {', '.join(updated)}")
    print(f"Run 'generate {slug}' to refresh docs.")


def cmd_show(args: argparse.Namespace) -> None:
    slug = args.slug
    sidecar = _load_sidecar(slug)

    if getattr(args, 'json', False):
        print(json.dumps(sidecar, indent=2))
        return

    uc = sidecar["user_content"]
    gen = sidecar["generated_sections"]

    print(f"=== Docs: {slug} ===")
    print(f"Headline:    {uc['headline']}")
    print(f"Status:      {uc['status_badge']}")
    print(f"Install:     {len(uc['install_steps'])} steps")
    print(f"Screenshots: {len(uc['screenshots'])}")
    print(f"Contact:     {uc['support_contact'] or '(none)'}")
    print(f"Releases:    {len(sidecar['releases'])}")

    if sidecar["releases"]:
        latest = sidecar["releases"][-1]
        print(f"  Latest:    {latest['version']} -- {latest['headline']}")

    print(f"Generated:   {_human_date(gen['last_generated_at'])}")
    active_sources = [k for k, v in gen["sources"].items() if v]
    print(f"Sources:     {', '.join(active_sources) if active_sources else '(none yet)'}")


def cmd_delete(args: argparse.Namespace) -> None:
    slug = args.slug
    path = _docs_path(slug)

    if not path.exists():
        _err(f"No docs sidecar for '{slug}'.")
        sys.exit(10)

    if not getattr(args, 'yes', False):
        _err(f"This will delete the docs sidecar for '{slug}'. Generated .md files are preserved.")
        _err("Pass --yes to confirm.")
        sys.exit(9)

    path.unlink()
    print(f"Docs sidecar deleted for '{slug}'. Generated .md files are preserved in the repo.")


# --------------------------------------------------------------------------- #
# CLI wiring                                                                  #
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="docs_tool.py",
        description="Auto-docs: generate and maintain project documentation."
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    # init
    p_init = sub.add_parser("init", help="Create docs sidecar from user_content on stdin")
    p_init.add_argument("slug")
    p_init.add_argument("--from-stdin", action="store_true", default=True)

    # generate
    p_gen = sub.add_parser("generate", help="Regenerate one or all doc files")
    p_gen.add_argument("slug")
    p_gen.add_argument("--only", help="Generate only this doc (README, SETUP, ARCHITECTURE, CHANGELOG)")
    p_gen.add_argument("--force", action="store_true", help="Overwrite non-auto-docs files")

    # release
    p_rel = sub.add_parser("release", help="Append a release from stdin")
    p_rel.add_argument("slug")
    p_rel.add_argument("--from-stdin", action="store_true", default=True)

    # update-content
    p_upd = sub.add_parser("update-content", help="Update user_content fields from stdin")
    p_upd.add_argument("slug")
    p_upd.add_argument("--from-stdin", action="store_true", default=True)

    # show
    p_show = sub.add_parser("show", help="Display docs sidecar state")
    p_show.add_argument("slug")
    p_show.add_argument("--json", action="store_true")

    # delete
    p_del = sub.add_parser("delete", help="Remove docs sidecar (preserves .md files)")
    p_del.add_argument("slug")
    p_del.add_argument("--yes", action="store_true")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "generate": cmd_generate,
        "release": cmd_release,
        "update-content": cmd_update_content,
        "show": cmd_show,
        "delete": cmd_delete,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
