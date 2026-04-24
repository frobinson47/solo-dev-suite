#!/usr/bin/env python3
"""
dashboard.py -- Cross-skill dashboard for Solo Dev Suite projects.

Reads a project's profile + all sidecar files and renders a unified
status view showing every skill's state in one glance.

Commands:
    status  <slug> [--json]                    # terminal dashboard
    render  <slug> [--output PATH] [--no-open] # write .md + .html, open browser

Exit codes:
    0  success
    1  slug not found
    2  suite install broken

Design notes:
  * No external deps. Pure stdlib. Same patterns as profile_io.py.
  * Each sidecar is optional — missing = "not run".
  * HTML is self-contained (inline CSS, no JS deps).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_DIR = SCRIPT_DIR.parent
PROFILES_DIR = SUITE_DIR / "profiles"

# Skill display order (matches lifecycle phases)
SKILL_ORDER = [
    "mvp-scope-guardian",
    "saas-pricing-architect",
    "adr-generator",
    "integration-mapper",
    "sprint-planner",
    "tech-debt-register",
    "testing-strategy",
    "security-audit",
    "launch-readiness",
    "auto-docs",
]

SKILL_LABELS = {
    "mvp-scope-guardian": "MVP Scope Guardian",
    "saas-pricing-architect": "SaaS Pricing Architect",
    "adr-generator": "ADR Generator",
    "integration-mapper": "Integration Mapper",
    "sprint-planner": "Sprint Planner",
    "tech-debt-register": "Tech Debt Register",
    "testing-strategy": "Testing Strategy",
    "security-audit": "Security Audit",
    "launch-readiness": "Launch Readiness",
    "auto-docs": "Auto Docs",
}


def _err(msg: str) -> None:
    print(f"[dashboard] {msg}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _days_since(iso_ts: str) -> Optional[int]:
    try:
        dt = datetime.fromisoformat(iso_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except (ValueError, TypeError):
        return None


def _days_until(date_str: str) -> Optional[int]:
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (target - datetime.now(timezone.utc)).days
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------- #
# Sidecar readers — one per skill                                             #
# --------------------------------------------------------------------------- #

def _read_sidecar(slug: str, suffix: str) -> Optional[Dict[str, Any]]:
    """Read a sidecar JSON file. Returns None if missing or corrupt."""
    path = PROFILES_DIR / f"{slug}.{suffix}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _skill_status(slug: str, profile: Dict[str, Any]) -> List[Dict[str, str]]:
    """Compute status for each skill. Returns list of {name, label, status, detail, last_run}."""
    last_runs = profile.get("last_skill_run", {})
    results = []

    for skill in SKILL_ORDER:
        label = SKILL_LABELS[skill]
        last_run = last_runs.get(skill)
        last_run_display = f"{_days_since(last_run)}d ago" if last_run and _days_since(last_run) is not None else None

        entry = {
            "name": skill,
            "label": label,
            "status": "--",
            "detail": "not run",
            "last_run": last_run_display or "never",
        }

        if skill == "mvp-scope-guardian":
            sc = _read_sidecar(slug, "scope")
            if sc:
                items = sc.get("features", [])
                lb = sum(1 for f in items if f.get("bucket") == "LAUNCH-BLOCKING")
                total = len(items)
                entry["status"] = "OK"
                entry["detail"] = f"{lb} launch-blocking, {total} total scoped"

        elif skill == "saas-pricing-architect":
            pr = _read_sidecar(slug, "pricing")
            if pr:
                versions = pr.get("versions", [])
                active = versions[-1] if versions else {}
                strategy = active.get("strategy", "?")
                tiers = len(active.get("tiers", []))
                ver = len(versions)
                entry["status"] = "OK"
                entry["detail"] = f"v{ver}, {strategy}, {tiers} tiers"

        elif skill == "adr-generator":
            adr = _read_sidecar(slug, "adr")
            if adr:
                records = adr.get("records", [])
                accepted = sum(1 for r in records if r.get("status") == "accepted")
                proposed = sum(1 for r in records if r.get("status") == "proposed")
                entry["status"] = "OK"
                entry["detail"] = f"{accepted} accepted, {proposed} proposed"

        elif skill == "integration-mapper":
            intg = _read_sidecar(slug, "integrations")
            if intg:
                services = intg.get("services", [])
                unhedged = sum(1 for s in services
                              if s.get("risk", {}).get("blast_radius") in ("high", "critical")
                              and not s.get("fallback_plan"))
                stale = sum(1 for s in services if s.get("is_stale"))
                total = len(services)
                if unhedged > 0:
                    entry["status"] = "WARN"
                    entry["detail"] = f"{unhedged} unhedged risk{'s' if unhedged != 1 else ''}, {total} tracked"
                else:
                    entry["status"] = "OK"
                    entry["detail"] = f"{total} tracked, all hedged"
                if stale:
                    entry["detail"] += f", {stale} stale"

        elif skill == "sprint-planner":
            sp = _read_sidecar(slug, "sprint")
            if sp:
                velocity = sp.get("velocity", {}).get("average_hours")
                countdown = sp.get("launch_countdown", {})
                signal = countdown.get("signal", "?")
                entry["status"] = "CRIT" if signal == "red" else ("WARN" if signal == "yellow" else "OK")
                vel_str = f"{velocity}h/wk" if velocity else "no data"
                entry["detail"] = f"velocity {vel_str}, countdown {signal}"

        elif skill == "tech-debt-register":
            td = _read_sidecar(slug, "techdebt")
            if td:
                items = td.get("items", [])
                open_count = sum(1 for i in items if i.get("status") == "open")
                critical = sum(1 for i in items
                              if i.get("status") == "open"
                              and i.get("impact") in ("critical", "high"))
                if critical > 0:
                    entry["status"] = "WARN"
                    entry["detail"] = f"{open_count} open, {critical} high/critical"
                elif open_count > 0:
                    entry["status"] = "OK"
                    entry["detail"] = f"{open_count} open, none critical"
                else:
                    entry["status"] = "OK"
                    entry["detail"] = "no open debt"

        elif skill == "testing-strategy":
            ts = _read_sidecar(slug, "testing")
            if ts:
                splits = ts.get("effort_splits", {})
                unit = splits.get("unit", "?")
                e2e = splits.get("e2e", "?")
                review = ts.get("last_reviewed")
                stale = False
                if review:
                    days = _days_since(review)
                    cadence = ts.get("review_cadence_days", 90)
                    if days and days > cadence:
                        stale = True
                entry["status"] = "WARN" if stale else "OK"
                entry["detail"] = f"unit {unit}%, e2e {e2e}%"
                if stale:
                    entry["detail"] += " (stale)"

        elif skill == "security-audit":
            sec = _read_sidecar(slug, "security")
            if sec:
                findings = sec.get("findings", [])
                criticals = sum(1 for f in findings
                               if f.get("severity") == "critical"
                               and f.get("status") not in ("resolved", "accepted"))
                highs = sum(1 for f in findings
                           if f.get("severity") == "high"
                           and f.get("status") not in ("resolved", "accepted"))
                signed = sec.get("signed_off", False)
                if criticals > 0:
                    entry["status"] = "CRIT"
                    entry["detail"] = f"{criticals} critical, {highs} high open"
                elif highs > 0:
                    entry["status"] = "WARN"
                    entry["detail"] = f"{highs} high open"
                else:
                    entry["status"] = "OK"
                    entry["detail"] = "clear" + (" (signed off)" if signed else "")

        elif skill == "launch-readiness":
            lr = _read_sidecar(slug, "readiness")
            if lr:
                categories = lr.get("categories", [])
                total = 0
                passed = 0
                for cat in categories:
                    for item in cat.get("items", []):
                        total += 1
                        if item.get("status") in ("pass", "accepted"):
                            passed += 1
                shippable = lr.get("is_shippable", False)
                if shippable:
                    entry["status"] = "OK"
                    entry["detail"] = f"{passed}/{total} passed, shippable"
                else:
                    entry["status"] = "CRIT"
                    entry["detail"] = f"{passed}/{total} passed, not shippable"

        elif skill == "auto-docs":
            docs = _read_sidecar(slug, "docs")
            if docs:
                last_gen = docs.get("last_generated_at")
                doc_count = len(docs.get("generated_docs", []))
                days = _days_since(last_gen) if last_gen else None
                entry["status"] = "OK"
                entry["detail"] = f"{doc_count} docs"
                if days is not None:
                    entry["detail"] += f", generated {days}d ago"

        # If skill has been run but no sidecar, mark as ran
        if entry["status"] == "--" and last_run:
            entry["status"] = "OK"
            entry["detail"] = f"last run {last_run_display}"

        results.append(entry)

    return results


# --------------------------------------------------------------------------- #
# Terminal output                                                             #
# --------------------------------------------------------------------------- #

def _render_terminal(profile: Dict[str, Any], skills: List[Dict[str, str]]) -> str:
    """Render the dashboard as terminal text."""
    name = profile.get("project_name", "?")
    slug = profile.get("project_slug", "?")
    phase = profile.get("current_phase", "?")
    launch = profile.get("launch_target_date")
    blockers = profile.get("blockers", [])
    services = profile.get("third_party_services", [])
    last_runs = profile.get("last_skill_run", {})

    # Header
    launch_str = ""
    if launch:
        days = _days_until(launch)
        if days is not None:
            if days < 0:
                launch_str = f"  |  Launch: {launch} (OVERDUE)"
            else:
                launch_str = f"  |  Launch: {launch} ({days}d)"
        else:
            launch_str = f"  |  Launch: {launch}"

    lines = []
    lines.append(f"\n  Dashboard: {name} ({slug})  |  Phase: {phase}{launch_str}")
    lines.append(f"  {'=' * 70}")
    lines.append("")

    # Skill table
    col_w = {"label": 24, "status": 8, "detail": 36}
    headers = {"label": "Skill", "status": "Status", "detail": "Detail"}
    header_line = f"  {headers['label']:<{col_w['label']}}  {headers['status']:<{col_w['status']}}  {headers['detail']}"
    lines.append(header_line)
    lines.append(f"  {'-' * col_w['label']}  {'-' * col_w['status']}  {'-' * col_w['detail']}")

    for s in skills:
        lines.append(f"  {s['label']:<{col_w['label']}}  {s['status']:<{col_w['status']}}  {s['detail']}")

    lines.append(f"  {'-' * col_w['label']}  {'-' * col_w['status']}  {'-' * col_w['detail']}")

    # Footer
    unhedged = sum(1 for svc in services
                   if svc.get("risk_level") in ("high", "critical")
                   and not svc.get("fallback"))

    lines.append(f"  Blockers : {len(blockers)} active")
    lines.append(f"  Services : {len(services)} tracked, {unhedged} unhedged")

    if last_runs:
        most_recent = max(last_runs.items(), key=lambda x: x[1])
        days = _days_since(most_recent[1])
        lines.append(f"  Last run : {most_recent[0]} ({days}d ago)" if days is not None else f"  Last run : {most_recent[0]}")

    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Markdown output                                                             #
# --------------------------------------------------------------------------- #

def _render_markdown(profile: Dict[str, Any], skills: List[Dict[str, str]]) -> str:
    """Render the dashboard as a Markdown document."""
    name = profile.get("project_name", "?")
    slug = profile.get("project_slug", "?")
    phase = profile.get("current_phase", "?")
    launch = profile.get("launch_target_date", "Not set")
    blockers = profile.get("blockers", [])
    services = profile.get("third_party_services", [])

    lines = [
        f"# Project Status: {name}",
        f"",
        f"_Generated {_now_iso()} UTC_",
        f"",
        f"| | |",
        f"|---|---|",
        f"| **Phase** | {phase} |",
        f"| **Launch** | {launch or 'Not set'} |",
        f"| **Blockers** | {len(blockers)} active |",
        f"| **Services** | {len(services)} tracked |",
        f"",
        f"## Skill Status",
        f"",
        f"| Skill | Status | Detail | Last Run |",
        f"|-------|--------|--------|----------|",
    ]

    for s in skills:
        lines.append(f"| {s['label']} | {s['status']} | {s['detail']} | {s['last_run']} |")

    if blockers:
        lines.append(f"\n## Active Blockers\n")
        for b in blockers:
            lines.append(f"- {b}")

    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# HTML output                                                                 #
# --------------------------------------------------------------------------- #

def _status_color(status: str) -> Tuple[str, str]:
    """Return (bg_color, text_color) for a status."""
    colors = {
        "OK":   ("#00b894", "#ffffff"),
        "WARN": ("#fdcb6e", "#2d3436"),
        "CRIT": ("#d63031", "#ffffff"),
        "--":   ("#636e72", "#ffffff"),
    }
    return colors.get(status, colors["--"])


def _render_html(profile: Dict[str, Any], skills: List[Dict[str, str]]) -> str:
    """Render the dashboard as a self-contained HTML file."""
    name = profile.get("project_name", "?")
    slug = profile.get("project_slug", "?")
    phase = profile.get("current_phase", "?")
    launch = profile.get("launch_target_date")
    blockers = profile.get("blockers", [])
    services = profile.get("third_party_services", [])
    last_runs = profile.get("last_skill_run", {})

    # Launch display
    launch_html = ""
    if launch:
        days = _days_until(launch)
        if days is not None:
            if days < 0:
                launch_html = f'<span class="badge badge-crit">OVERDUE by {abs(days)}d</span>'
            elif days <= 7:
                launch_html = f'<span class="badge badge-warn">{days}d to launch</span>'
            else:
                launch_html = f'<span class="badge badge-ok">{days}d to launch</span>'
        else:
            launch_html = launch
    else:
        launch_html = '<span class="badge badge-muted">No date set</span>'

    # Phase badge
    phase_colors = {
        "idea": "#a29bfe", "scope": "#6c5ce7", "architecture": "#0984e3",
        "build": "#00b894", "ship": "#fdcb6e", "grow": "#e17055", "sustain": "#636e72",
    }
    phase_bg = phase_colors.get(phase, "#636e72")

    # Skill cards
    cards_html = ""
    for s in skills:
        bg, fg = _status_color(s["status"])
        cards_html += f'''
        <div class="card">
            <div class="card-header">
                <span class="status-dot" style="background:{bg}"></span>
                <span class="card-title">{s['label']}</span>
                <span class="status-badge" style="background:{bg};color:{fg}">{s['status']}</span>
            </div>
            <div class="card-detail">{s['detail']}</div>
            <div class="card-meta">Last run: {s['last_run']}</div>
        </div>'''

    # Summary stats
    ok_count = sum(1 for s in skills if s["status"] == "OK")
    warn_count = sum(1 for s in skills if s["status"] == "WARN")
    crit_count = sum(1 for s in skills if s["status"] == "CRIT")
    not_run = sum(1 for s in skills if s["status"] == "--")

    unhedged = sum(1 for svc in services
                   if svc.get("risk_level") in ("high", "critical")
                   and not svc.get("fallback"))

    # Blockers HTML
    blockers_html = ""
    if blockers:
        items = "".join(f"<li>{b}</li>" for b in blockers)
        blockers_html = f'''
        <div class="section">
            <h2>Active Blockers</h2>
            <ul class="blocker-list">{items}</ul>
        </div>'''

    # Most recent run
    last_run_html = ""
    if last_runs:
        most_recent = max(last_runs.items(), key=lambda x: x[1])
        days = _days_since(most_recent[1])
        last_run_html = f"{most_recent[0]} ({days}d ago)" if days is not None else most_recent[0]

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard: {name}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        background: #0a0a1a;
        color: #e0e0e0;
        min-height: 100vh;
        padding: 2rem;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}

    /* Header */
    .header {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 1rem;
        margin-bottom: 2rem;
        padding-bottom: 1.5rem;
        border-bottom: 1px solid #2d2d4a;
    }}
    .header h1 {{
        font-size: 1.75rem;
        font-weight: 700;
        color: #ffffff;
        flex: 1;
    }}
    .header h1 .slug {{ color: #636e72; font-weight: 400; font-size: 1rem; }}
    .badge {{
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .badge-phase {{ background: {phase_bg}; color: #fff; }}
    .badge-ok {{ background: #00b894; color: #fff; }}
    .badge-warn {{ background: #fdcb6e; color: #2d3436; }}
    .badge-crit {{ background: #d63031; color: #fff; }}
    .badge-muted {{ background: #2d2d4a; color: #b2bec3; }}

    /* Summary bar */
    .summary-bar {{
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        margin-bottom: 2rem;
    }}
    .summary-item {{
        background: #16213e;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        flex: 1;
        min-width: 140px;
    }}
    .summary-item .label {{ font-size: 0.75rem; color: #b2bec3; text-transform: uppercase; letter-spacing: 0.08em; }}
    .summary-item .value {{ font-size: 1.5rem; font-weight: 700; margin-top: 0.25rem; }}
    .summary-item .value.green {{ color: #00b894; }}
    .summary-item .value.amber {{ color: #fdcb6e; }}
    .summary-item .value.red {{ color: #d63031; }}
    .summary-item .value.gray {{ color: #636e72; }}

    /* Cards grid */
    .cards {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }}
    .card {{
        background: #16213e;
        border-radius: 8px;
        padding: 1.25rem;
        border-left: 4px solid #2d2d4a;
        transition: border-color 0.2s;
    }}
    .card:hover {{ border-left-color: #6c5ce7; }}
    .card-header {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.75rem;
    }}
    .status-dot {{
        width: 10px; height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
    }}
    .card-title {{
        font-weight: 600;
        font-size: 0.95rem;
        flex: 1;
        color: #ffffff;
    }}
    .status-badge {{
        font-size: 0.7rem;
        font-weight: 700;
        padding: 0.15rem 0.5rem;
        border-radius: 3px;
        letter-spacing: 0.05em;
    }}
    .card-detail {{
        font-size: 0.875rem;
        color: #b2bec3;
        line-height: 1.5;
    }}
    .card-meta {{
        font-size: 0.75rem;
        color: #636e72;
        margin-top: 0.5rem;
    }}

    /* Sections */
    .section {{
        background: #16213e;
        border-radius: 8px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }}
    .section h2 {{
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 0.75rem;
        color: #dfe6e9;
    }}
    .blocker-list {{
        list-style: none;
        padding: 0;
    }}
    .blocker-list li {{
        padding: 0.5rem 0;
        border-bottom: 1px solid #2d2d4a;
        font-size: 0.875rem;
        color: #fab1a0;
    }}
    .blocker-list li:last-child {{ border-bottom: none; }}

    /* Footer */
    .footer {{
        text-align: center;
        color: #636e72;
        font-size: 0.75rem;
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #2d2d4a;
    }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{name} <span class="slug">{slug}</span></h1>
        <span class="badge badge-phase">{phase}</span>
        {launch_html}
    </div>

    <div class="summary-bar">
        <div class="summary-item">
            <div class="label">Healthy</div>
            <div class="value green">{ok_count}</div>
        </div>
        <div class="summary-item">
            <div class="label">Warnings</div>
            <div class="value amber">{warn_count}</div>
        </div>
        <div class="summary-item">
            <div class="label">Critical</div>
            <div class="value red">{crit_count}</div>
        </div>
        <div class="summary-item">
            <div class="label">Not Run</div>
            <div class="value gray">{not_run}</div>
        </div>
        <div class="summary-item">
            <div class="label">Blockers</div>
            <div class="value {"red" if blockers else "green"}">{len(blockers)}</div>
        </div>
        <div class="summary-item">
            <div class="label">Services</div>
            <div class="value {"amber" if unhedged else "green"}">{len(services)}</div>
        </div>
    </div>

    <div class="cards">{cards_html}
    </div>

    {blockers_html}

    <div class="footer">
        Solo Dev Suite Dashboard &middot; Generated {_now_iso()} UTC
        {f" &middot; Last skill run: {last_run_html}" if last_run_html else ""}
    </div>
</div>
</body>
</html>'''


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def _load_profile(slug: str) -> Optional[Dict[str, Any]]:
    path = PROFILES_DIR / f"{slug}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def cmd_status(args: argparse.Namespace) -> int:
    """Terminal dashboard for a project."""
    profile = _load_profile(args.slug)
    if profile is None:
        _err(f"No profile found for slug '{args.slug}'.")
        return 1

    skills = _skill_status(args.slug, profile)

    if args.json:
        print(json.dumps({
            "slug": args.slug,
            "phase": profile.get("current_phase"),
            "launch_target": profile.get("launch_target_date"),
            "blockers": len(profile.get("blockers", [])),
            "skills": skills,
        }, indent=2))
        return 0

    print(_render_terminal(profile, skills))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    """Write PROJECT_STATUS.md + .html and open in browser."""
    profile = _load_profile(args.slug)
    if profile is None:
        _err(f"No profile found for slug '{args.slug}'.")
        return 1

    skills = _skill_status(args.slug, profile)

    # Determine output paths
    if args.output:
        base = Path(args.output)
        md_path = base.with_suffix(".md")
        html_path = base.with_suffix(".html")
    else:
        repo_path = profile.get("repository_path")
        if repo_path and Path(repo_path).exists():
            md_path = Path(repo_path) / "PROJECT_STATUS.md"
            html_path = Path(repo_path) / "PROJECT_STATUS.html"
        else:
            out_dir = SUITE_DIR / "status"
            out_dir.mkdir(parents=True, exist_ok=True)
            md_path = out_dir / f"{args.slug}_STATUS.md"
            html_path = out_dir / f"{args.slug}_STATUS.html"

    # Write markdown
    md_content = _render_markdown(profile, skills)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = md_path.with_suffix(".md.tmp")
    tmp.write_text(md_content, encoding="utf-8")
    tmp.replace(md_path)
    print(f"Markdown: {md_path}")

    # Write HTML
    html_content = _render_html(profile, skills)
    tmp = html_path.with_suffix(".html.tmp")
    tmp.write_text(html_content, encoding="utf-8")
    tmp.replace(html_path)
    print(f"HTML:     {html_path}")

    # Auto-open in browser
    if not args.no_open:
        webbrowser.open(html_path.as_uri())
        print("Opened in browser.")

    return 0


# --------------------------------------------------------------------------- #
# Arg parsing                                                                 #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dashboard",
        description="Cross-skill dashboard for Solo Dev Suite projects.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Terminal dashboard for a project.")
    p_status.add_argument("slug", help="Project slug.")
    p_status.add_argument("--json", action="store_true", help="Machine-readable output.")
    p_status.set_defaults(func=cmd_status)

    p_render = sub.add_parser("render", help="Write PROJECT_STATUS.md + .html and open in browser.")
    p_render.add_argument("slug", help="Project slug.")
    p_render.add_argument("--output", help="Base output path (writes .md and .html).")
    p_render.add_argument("--no-open", action="store_true", help="Skip auto-opening in browser.")
    p_render.set_defaults(func=cmd_render)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
