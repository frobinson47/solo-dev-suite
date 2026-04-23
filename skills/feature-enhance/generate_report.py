#!/usr/bin/env python3
"""
generate_report.py — FMR Feature Enhancement Skill
Assembles the final FEATURE_ENHANCEMENTS.md report from:
  - context.json  (from discover.py)
  - research.json (from Claude's web research phase)

Usage:
    python generate_report.py context.json research.json \
        [--output FEATURE_ENHANCEMENTS.md]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# ─── Stub categorization helpers ──────────────────────────────────────────────

STUB_TYPE_LABELS = {
    "comment":          "📌 TODO/FIXME Comment",
    "python_stub":      "🐍 Unimplemented Python Function",
    "js_stub":          "⚡ JS/TS Not-Implemented Throw",
    "python_pass":      "🐍 Empty Python Pass Block",
    "null_stub":        "🚫 Null Return Stub",
    "log_stub":         "📋 Console.log TODO",
    "placeholder":      "🔲 Placeholder Content",
    "coming_soon":      "🚧 Coming Soon",
    "not_implemented":  "❌ Not Implemented",
    "lorem":            "📝 Lorem Ipsum Placeholder",
    "jsx_stub":         "⚡ JSX Stub Block",
}

def group_stubs(stubs: list) -> dict:
    """Group stubs by type for the report."""
    grouped = {}
    for s in stubs:
        t = s.get("type", "other")
        grouped.setdefault(t, []).append(s)
    return grouped


def dedupe_routes(routes: list) -> list:
    """Deduplicate and sort routes for readability."""
    seen = {}
    for r in routes:
        path = r.get("path", "")
        if path not in seen:
            seen[path] = r
    return sorted(seen.values(), key=lambda r: r.get("path", ""))


def priority_badge(priority: str) -> str:
    badges = {
        "critical": "🔴 Critical",
        "high":     "🟠 High",
        "medium":   "🟡 Medium",
        "low":      "🟢 Low",
    }
    return badges.get(priority.lower(), priority)


def effort_badge(effort: str) -> str:
    badges = {
        "small":  "⚡ Small  (< 1 day)",
        "medium": "🔧 Medium (1–3 days)",
        "large":  "🏗️ Large  (1–2 weeks)",
        "xl":     "🚀 XL     (2+ weeks)",
    }
    return badges.get(effort.lower(), effort)


# ─── Report Builder ───────────────────────────────────────────────────────────

def build_report(ctx: dict, research: dict) -> str:
    project = ctx.get("project_name", "Unknown Project")
    domain  = ctx.get("domain", "web-app")
    ts      = datetime.now().strftime("%Y-%m-%d %H:%M")
    stats   = ctx.get("stats", {})
    summary = ctx.get("summary", {})
    git     = ctx.get("git", {})

    lines = []
    a = lines.append  # shortcut

    # ── Header ────────────────────────────────────────────────────────────────
    a(f"# 🔍 Feature Enhancement Report — {project}")
    a(f"")
    a(f"> **Generated:** {ts}  ")
    a(f"> **Domain:** `{domain}`  ")
    a(f"> **Root:** `{ctx.get('root', '')}`  ")
    a(f"> **Source:** FMR Feature Enhancement Skill v1.0")
    a(f"")
    a(f"---")
    a(f"")

    # ── Table of Contents ─────────────────────────────────────────────────────
    a(f"## 📋 Table of Contents")
    a(f"")
    a(f"1. [Project Snapshot](#1-project-snapshot)")
    a(f"2. [Tech Stack](#2-tech-stack)")
    a(f"3. [Current Features Inventory](#3-current-features-inventory)")
    a(f"4. [Incomplete & Stub Work](#4-incomplete--stub-work)")
    a(f"5. [Competitive Landscape](#5-competitive-landscape)")
    a(f"6. [Recommended Feature Enhancements](#6-recommended-feature-enhancements)")
    a(f"7. [Enhancement Priority Matrix](#7-enhancement-priority-matrix)")
    a(f"8. [Quick Wins](#8-quick-wins)")
    a(f"9. [Next Steps](#9-next-steps)")
    a(f"")
    a(f"---")
    a(f"")

    # ── 1. Project Snapshot ───────────────────────────────────────────────────
    a(f"## 1. Project Snapshot")
    a(f"")
    a(f"| Metric | Value |")
    a(f"|--------|-------|")
    a(f"| Total Source Files | {stats.get('total_files', 'N/A')} |")
    a(f"| Total Lines of Code | {stats.get('total_lines', 0):,} |")
    a(f"| Routes / Pages | {summary.get('total_routes', 0)} |")
    a(f"| Components | {summary.get('total_components', 0)} |")
    a(f"| Stub / TODO Items | {summary.get('total_stubs', 0)} |")
    a(f"| Empty Functions | {summary.get('total_empty_fns', 0)} |")
    a(f"| Feature Flags | {summary.get('total_feature_flags', 0)} |")
    a(f"")

    if git.get("recent_commits"):
        a(f"### Recent Git Activity (last 20 commits)")
        a(f"```")
        for commit in git["recent_commits"][:10]:
            a(f"{commit}")
        a(f"```")
        a(f"")

    if git.get("branches"):
        a(f"**Active Branches:** " + ", ".join(f"`{b}`" for b in git["branches"][:8]))
        a(f"")

    a(f"---")
    a(f"")

    # ── 2. Tech Stack ─────────────────────────────────────────────────────────
    a(f"## 2. Tech Stack")
    a(f"")

    frameworks = ctx.get("frameworks", [])
    databases  = ctx.get("databases", [])
    auth_tools = ctx.get("auth_tools", [])
    languages  = ctx.get("languages", [])

    if languages:
        a(f"### Languages (by file count)")
        a(f"")
        for lang in languages[:6]:
            a(f"- `{lang['ext']}` — {lang['count']} files")
        a(f"")

    if frameworks:
        a(f"### Frameworks & Runtime")
        a(f"")
        for fw in frameworks:
            a(f"- `{fw}`")
        a(f"")

    if databases:
        a(f"### Databases & ORMs")
        a(f"")
        for db in databases:
            a(f"- `{db}`")
        a(f"")

    if auth_tools:
        a(f"### Authentication")
        a(f"")
        for at in auth_tools:
            a(f"- `{at}`")
        a(f"")

    # Key runtime deps
    runtime = ctx.get("runtime_deps", [])
    if runtime:
        top = runtime[:20]
        a(f"### Key Dependencies")
        a(f"```")
        a("  ".join(top))
        a(f"```")
        a(f"")

    # Env vars signal integrations
    env_vars = ctx.get("env_vars", [])
    if env_vars:
        a(f"### Env / Integrations Detected")
        a(f"")
        for ev in env_vars:
            a(f"- `{ev}`")
        a(f"")

    a(f"---")
    a(f"")

    # ── 3. Current Features Inventory ─────────────────────────────────────────
    a(f"## 3. Current Features Inventory")
    a(f"")

    routes = dedupe_routes(ctx.get("routes", []))
    if routes:
        pages = [r for r in routes if r.get("type") in {"page", "route"}]
        apis  = [r for r in routes if r.get("type") == "api"]

        if pages:
            a(f"### Pages / Views ({len(pages)})")
            a(f"")
            a(f"| Route | File |")
            a(f"|-------|------|")
            for r in pages[:50]:
                a(f"| `{r['path']}` | `{r.get('file', '')}` |")
            if len(pages) > 50:
                a(f"| ... and {len(pages) - 50} more | |")
            a(f"")

        if apis:
            a(f"### API Endpoints ({len(apis)})")
            a(f"")
            a(f"| Endpoint | File |")
            a(f"|----------|------|")
            for r in apis[:30]:
                a(f"| `{r['path']}` | `{r.get('file', '')}` |")
            if len(apis) > 30:
                a(f"| ... and {len(apis) - 30} more | |")
            a(f"")
    else:
        a(f"> ℹ️ No explicit routes detected — project may use dynamic routing or a non-standard structure.")
        a(f"")

    components = ctx.get("components", [])
    if components:
        a(f"### UI Components ({len(components)})")
        a(f"")
        comp_names = [c["name"] for c in components[:30]]
        a(", ".join(f"`{n}`" for n in comp_names))
        if len(components) > 30:
            a(f"  \n... and {len(components) - 30} more.")
        a(f"")

    feature_flags = ctx.get("feature_flags", [])
    if feature_flags:
        a(f"### Feature Flags ({len(feature_flags)})")
        a(f"")
        for ff in feature_flags:
            a(f"- `{ff['flag']}` — `{ff.get('file', '')}`")
        a(f"")

    a(f"---")
    a(f"")

    # ── 4. Incomplete & Stub Work ─────────────────────────────────────────────
    a(f"## 4. Incomplete & Stub Work")
    a(f"")

    stubs   = ctx.get("stubs", [])
    empties = ctx.get("empty_functions", [])

    if not stubs and not empties:
        a(f"> ✅ No obvious stubs, TODOs, or empty functions detected.")
        a(f"")
    else:
        if stubs:
            grouped = group_stubs(stubs)
            a(f"### By Type")
            a(f"")
            for stype, items in sorted(grouped.items(), key=lambda x: -len(x[1])):
                label = STUB_TYPE_LABELS.get(stype, stype)
                a(f"#### {label} ({len(items)})")
                a(f"")
                a(f"| File | Line | Snippet |")
                a(f"|------|------|---------|")
                for item in items[:10]:
                    snippet = item.get("snippet", "").replace("|", "\\|")[:80]
                    a(f"| `{item.get('file', '')}` | {item.get('line', '')} | `{snippet}` |")
                if len(items) > 10:
                    a(f"| ... and {len(items) - 10} more | | |")
                a(f"")

        if empties:
            a(f"### Empty / Stub Python Functions ({len(empties)})")
            a(f"")
            a(f"| File | Function | Line |")
            a(f"|------|----------|------|")
            for ef in empties[:20]:
                a(f"| `{ef['file']}` | `{ef['function']}` | {ef['line']} |")
            a(f"")

    a(f"---")
    a(f"")

    # ── 5. Competitive Landscape ───────────────────────────────────────────────
    a(f"## 5. Competitive Landscape")
    a(f"")

    competitors = research.get("competitors", [])
    if competitors:
        a(f"The following similar applications and platforms were analyzed for feature inspiration:")
        a(f"")
        for comp in competitors:
            a(f"### {comp.get('name', 'Unknown')}")
            a(f"")
            if comp.get("url"):
                a(f"**URL:** {comp['url']}")
            if comp.get("description"):
                a(f"")
                a(f"{comp['description']}")
            if comp.get("notable_features"):
                a(f"")
                a(f"**Notable Features:**")
                for feat in comp["notable_features"]:
                    a(f"- {feat}")
            if comp.get("differentiators"):
                a(f"")
                a(f"**What Sets It Apart:**")
                for d in comp["differentiators"]:
                    a(f"- {d}")
            a(f"")
    else:
        a(f"> ℹ️ No competitive research data provided. Run the web research phase to populate this section.")
        a(f"")

    a(f"---")
    a(f"")

    # ── 6. Recommended Feature Enhancements ────────────────────────────────────
    a(f"## 6. Recommended Feature Enhancements")
    a(f"")

    enhancements = research.get("enhancements", [])
    if enhancements:
        for i, enh in enumerate(enhancements, 1):
            a(f"### {i}. {enh.get('title', 'Enhancement')}")
            a(f"")
            a(f"**Priority:** {priority_badge(enh.get('priority', 'medium'))}  ")
            a(f"**Effort:** {effort_badge(enh.get('effort', 'medium'))}  ")
            a(f"**Category:** {enh.get('category', 'General')}  ")
            a(f"")
            if enh.get("description"):
                a(enh["description"])
                a(f"")
            if enh.get("rationale"):
                a(f"**Why this matters:** {enh['rationale']}")
                a(f"")
            if enh.get("implementation_notes"):
                a(f"**Implementation Notes:**")
                a(f"")
                if isinstance(enh["implementation_notes"], list):
                    for note in enh["implementation_notes"]:
                        a(f"- {note}")
                else:
                    a(enh["implementation_notes"])
                a(f"")
            if enh.get("seen_in"):
                a(f"**Seen In:** " + ", ".join(enh["seen_in"]))
                a(f"")
            a(f"---")
            a(f"")
    else:
        a(f"> ℹ️ No enhancement data provided yet. Complete the research phase.")
        a(f"")

    # ── 7. Priority Matrix ────────────────────────────────────────────────────
    a(f"## 7. Enhancement Priority Matrix")
    a(f"")

    if enhancements:
        a(f"| # | Feature | Priority | Effort | Category |")
        a(f"|---|---------|----------|--------|----------|")
        for i, enh in enumerate(enhancements, 1):
            a(f"| {i} | {enh.get('title', '')} | {priority_badge(enh.get('priority','medium'))} | {effort_badge(enh.get('effort','medium'))} | {enh.get('category','')} |")
        a(f"")
    else:
        a(f"> No matrix data yet.")
        a(f"")

    a(f"---")
    a(f"")

    # ── 8. Quick Wins ─────────────────────────────────────────────────────────
    a(f"## 8. Quick Wins")
    a(f"")
    a(f"Items that deliver immediate value with minimal effort:")
    a(f"")

    # Pull small/high items from enhancements
    quick = [e for e in enhancements
             if e.get("effort") in {"small"} or
             (e.get("priority") in {"critical", "high"} and e.get("effort") == "small")]

    # Also pull from stubs (finish existing work = quick win)
    if stubs:
        todo_count = sum(1 for s in stubs if s.get("type") == "comment")
        if todo_count:
            a(f"- **Finish {todo_count} TODO/FIXME items** — existing stub work is partially done. "
              f"Resolve these before adding new features.")
    if empties:
        a(f"- **Implement {len(empties)} empty functions** — these are scaffolded but non-functional.")
    if quick:
        for q in quick:
            a(f"- **{q['title']}** — {q.get('description', '')[:120]}")
    if not stubs and not empties and not quick:
        a(f"> No obvious quick wins identified yet.")
    a(f"")

    a(f"---")
    a(f"")

    # ── 9. Next Steps ─────────────────────────────────────────────────────────
    a(f"## 9. Next Steps")
    a(f"")
    a(f"Suggested order of operations:")
    a(f"")
    a(f"1. **Resolve existing stubs first** — shipping unfinished features creates technical debt that compounds.")
    a(f"2. **Implement Quick Wins** — fast ROI, builds momentum.")
    a(f"3. **Prioritize Critical / High items** from the enhancement list.")
    a(f"4. **Validate with real users** before committing to XL-effort items.")
    a(f"5. **Re-run this skill** after each sprint to keep the enhancement list fresh.")
    a(f"")
    a(f"---")
    a(f"")
    a(f"*Report generated by FMR Feature Enhancement Skill — FMR Digital, LLC*")

    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("context",  help="Path to context.json from discover.py")
    parser.add_argument("research", nargs="?", default=None,
                        help="Path to research.json from Claude's web research phase")
    parser.add_argument("--output", "-o", default="FEATURE_ENHANCEMENTS.md",
                        help="Output report path")
    args = parser.parse_args()

    # Load context
    try:
        ctx = json.loads(Path(args.context).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR loading context: {e}", file=sys.stderr)
        sys.exit(1)

    # Load research (or use empty shell)
    if args.research and Path(args.research).exists():
        try:
            research = json.loads(Path(args.research).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"WARNING: Could not load research.json: {e}", file=sys.stderr)
            research = {}
    else:
        research = {}

    report = build_report(ctx, research)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"[generate_report] Report written to {out}", file=sys.stderr)
    print(f"REPORT_PATH:{out}")


if __name__ == "__main__":
    main()
