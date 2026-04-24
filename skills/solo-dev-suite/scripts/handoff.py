#!/usr/bin/env python3
"""
handoff.py -- Generate a comprehensive project handoff document.

Aggregates all skill outputs from a project profile into a single
PROJECT_HANDOFF.md: scope decisions, ADRs, pricing strategy, security
posture, tech debt inventory, sprint status, integrations, and testing.

Commands:
    generate <slug> [--mode developer|buyer] [--output PATH]

Modes:
    developer   Architecture, tech debt, testing, sprint status (default)
    buyer       Adds pricing strategy, market positioning, business model

Exit codes:
    0  success
    1  slug not found
    2  suite install broken
    3  no repo path configured (can't find docs/)

Design notes:
  * No external deps. Pure stdlib. Same patterns as profile_io.py.
  * Reads profile JSON + docs/*.md files from the project repo.
  * Output is a single Markdown file. Sections are included conditionally
    based on what data exists -- missing sections just get a note.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_DIR = SCRIPT_DIR.parent
PROFILES_DIR = SUITE_DIR / "profiles"


def _err(msg: str) -> None:
    print(f"[handoff] {msg}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _read_doc(repo_path: Path, *rel_parts: str) -> Optional[str]:
    """Try to read a doc file from the repo. Returns None if missing."""
    path = repo_path.joinpath(*rel_parts)
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


def _section(title: str, content: Optional[str], fallback: str = "_No data available. Run the relevant skill to populate._") -> str:
    """Format a markdown section, using fallback if content is empty."""
    body = content.strip() if content else fallback
    return f"## {title}\n\n{body}\n\n"


def _profile_summary(profile: Dict[str, Any]) -> str:
    """Generate the project overview section from profile data."""
    lines = [
        f"| Field | Value |",
        f"|-------|-------|",
        f"| **Name** | {profile.get('project_name', '?')} |",
        f"| **Slug** | {profile.get('project_slug', '?')} |",
        f"| **Type** | {profile.get('project_type', '?')} |",
        f"| **Phase** | {profile.get('current_phase', '?')} |",
        f"| **Stack** | {', '.join(profile.get('primary_stack', []))} |",
        f"| **Hosting** | {profile.get('hosting', '?')} |",
        f"| **Target Users** | {profile.get('target_users', '?')} |",
        f"| **Business Model** | {profile.get('business_model', '?')} |",
        f"| **Hours/Week** | {profile.get('available_hours_per_week', '?')} |",
        f"| **Launch Target** | {profile.get('launch_target_date') or 'Not set'} |",
    ]
    return "\n".join(lines)


def _blockers_section(profile: Dict[str, Any]) -> Optional[str]:
    """Format blockers if any exist."""
    blockers = profile.get("blockers", [])
    if not blockers:
        return None
    lines = [f"- {b}" for b in blockers]
    return "\n".join(lines)


def _services_section(profile: Dict[str, Any]) -> Optional[str]:
    """Format third-party services table."""
    services = profile.get("third_party_services", [])
    if not services:
        return None
    lines = [
        "| Service | Purpose | Risk | Fallback |",
        "|---------|---------|------|----------|",
    ]
    for s in services:
        fallback = s.get("fallback") or "None"
        lines.append(f"| {s['name']} | {s['purpose']} | {s['risk_level']} | {fallback} |")
    return "\n".join(lines)


def _skill_runs_section(profile: Dict[str, Any]) -> Optional[str]:
    """Format last skill runs."""
    runs = profile.get("last_skill_run", {})
    if not runs:
        return "_No skills have been run on this project yet._"
    lines = [
        "| Skill | Last Run |",
        "|-------|----------|",
    ]
    for name, ts in sorted(runs.items()):
        lines.append(f"| {name} | {ts} |")
    return "\n".join(lines)


def _pricing_section(profile: Dict[str, Any]) -> Optional[str]:
    """Format pricing model summary from profile."""
    pricing = profile.get("pricing_model")
    if not pricing:
        return None

    lines = []
    if isinstance(pricing, dict):
        strategy = pricing.get("strategy", "?")
        lines.append(f"**Strategy:** {strategy}")

        tiers = pricing.get("tiers", [])
        if tiers:
            lines.append("")
            lines.append("| Tier | Price | Features |")
            lines.append("|------|-------|----------|")
            for t in tiers:
                name = t.get("name", "?")
                price = t.get("price", "?")
                features = ", ".join(t.get("features", [])[:3])
                if len(t.get("features", [])) > 3:
                    features += "..."
                lines.append(f"| {name} | {price} | {features} |")

        value_metric = pricing.get("value_metric")
        if value_metric:
            lines.append(f"\n**Value Metric:** {value_metric}")

    return "\n".join(lines) if lines else None


def generate_handoff(profile: Dict[str, Any], mode: str, output_path: Path) -> int:
    """Build and write the handoff document."""
    slug = profile.get("project_slug", "unknown")
    repo_path_str = profile.get("repository_path")

    parts: List[str] = []

    # Header
    parts.append(f"# Project Handoff: {profile.get('project_name', slug)}\n")
    parts.append(f"_Generated {_now_iso()} UTC | Mode: {mode}_\n\n")
    parts.append("---\n\n")

    # Overview
    parts.append(_section("Project Overview", _profile_summary(profile)))

    # Description
    parts.append(_section("Description", profile.get("description")))

    # Blockers
    blockers = _blockers_section(profile)
    if blockers:
        parts.append(_section("Active Blockers", blockers))

    # Third-party services / integrations
    services = _services_section(profile)
    if services:
        parts.append(_section("Third-Party Services", services))

    # Try to read docs from the repo
    repo_path = Path(repo_path_str) if repo_path_str else None
    has_repo = repo_path and repo_path.exists()

    if has_repo:
        # Scope
        scope = _read_doc(repo_path, "docs", "MVP_SCOPE.md")
        parts.append(_section("MVP Scope", scope))

        # Architecture / ADRs
        adr_index = _read_doc(repo_path, "docs", "adr", "index.md")
        arch = _read_doc(repo_path, "docs", "ARCHITECTURE.md")
        if arch or adr_index:
            arch_content = ""
            if arch:
                arch_content += arch.strip() + "\n\n"
            if adr_index:
                arch_content += "### Architecture Decision Records\n\n" + adr_index.strip()
            parts.append(_section("Architecture", arch_content))
        else:
            parts.append(_section("Architecture", None))

        # Security
        security = _read_doc(repo_path, "docs", "SECURITY_AUDIT.md")
        parts.append(_section("Security Posture", security))

        # Tech Debt
        tech_debt = _read_doc(repo_path, "docs", "TECH_DEBT.md")
        parts.append(_section("Tech Debt", tech_debt))

        # Testing
        testing = _read_doc(repo_path, "docs", "TESTING_STRATEGY.md")
        parts.append(_section("Testing Strategy", testing))

        # Sprint / Roadmap
        sprint = _read_doc(repo_path, "docs", "SPRINT_PLAN.md")
        parts.append(_section("Sprint Plan", sprint))

        # Integrations doc
        integrations = _read_doc(repo_path, "docs", "INTEGRATIONS.md")
        if integrations:
            parts.append(_section("Integration Details", integrations))

        # Buyer mode extras
        if mode == "buyer":
            pricing = _read_doc(repo_path, "docs", "PRICING.md")
            if pricing:
                parts.append(_section("Pricing Strategy (Full)", pricing))
            elif _pricing_section(profile):
                parts.append(_section("Pricing Strategy", _pricing_section(profile)))
            else:
                parts.append(_section("Pricing Strategy", None))

            launch = _read_doc(repo_path, "docs", "LAUNCH_READINESS.md")
            parts.append(_section("Launch Readiness", launch))
    else:
        if mode == "buyer":
            pricing_content = _pricing_section(profile)
            if pricing_content:
                parts.append(_section("Pricing Strategy", pricing_content))

        parts.append(_section("Repository Documents",
                              "_No repository path configured. Set `repository_path` in the profile to include docs._"))

    # Skill coverage
    parts.append(_section("Skill Run History", _skill_runs_section(profile)))

    # Notes
    notes = profile.get("notes", "").strip()
    if notes:
        parts.append(_section("Notes", notes))

    # Write
    content = "".join(parts)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(output_path)

    print(f"Handoff document written: {output_path}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate a handoff document for a project."""
    path = PROFILES_DIR / f"{args.slug}.json"
    if not path.exists():
        _err(f"No profile found for slug '{args.slug}'.")
        return 1

    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _err(f"Profile corrupted: {e}")
        return 2

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        repo_path = profile.get("repository_path")
        if repo_path and Path(repo_path).exists():
            output_path = Path(repo_path) / "PROJECT_HANDOFF.md"
        else:
            output_path = PROFILES_DIR.parent / f"handoffs" / f"{args.slug}_HANDOFF.md"

    return generate_handoff(profile, args.mode, output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handoff",
        description="Generate a comprehensive project handoff document.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Generate PROJECT_HANDOFF.md for a project.")
    p_gen.add_argument("slug", help="Project slug.")
    p_gen.add_argument("--mode", choices=["developer", "buyer"], default="developer",
                       help="Handoff mode: 'developer' (default) or 'buyer'.")
    p_gen.add_argument("--output", help="Custom output path. Default: <repo>/PROJECT_HANDOFF.md")
    p_gen.set_defaults(func=cmd_generate)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
