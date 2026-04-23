---
name: feature-enhance
description: >
  Comprehensive feature-enhancement discovery skill. Points at any codebase — the current
  Claude Code workspace, a local source folder, or a Forgejo/Git repo URL — scans the full
  stack, inventories existing features, surfaces incomplete/stub work, then researches
  comparable apps and platforms to generate a prioritized list of value-add enhancements.
  Outputs a structured FEATURE_ENHANCEMENTS.md report.

  Trigger whenever the user says: "feature enhancement", "what features are we missing",
  "analyze my codebase for improvements", "compare to competitors", "what should I add next",
  "audit my app", "run the enhancement skill", "scan for TODOs and features", "what else
  should this do", or points at a project and asks for improvement ideas. Also triggers when
  user wants to know how their app stacks up against similar tools or what features
  competitors have that they don't.
---

# Feature Enhancement Skill

Scans a codebase, inventories its stack and current feature surface, identifies incomplete
work, and then uses web research to surface prioritized feature enhancements drawn from
comparable real-world products.

**Output:** `FEATURE_ENHANCEMENTS.md` in the project root (or a specified output dir).

---

## When to Use

- User wants to know what features their app is missing
- User wants a competitive analysis relative to their project domain
- User wants to inventory existing features + find TODOs/stubs
- User wants a research-backed feature roadmap
- Before starting a new sprint or planning cycle
- After inheriting or onboarding to an existing codebase

## When NOT to Use

- Single-file scripts or CLI tools with no feature surface — just answer directly
- User wants UI improvements (use the `design-loop` skill instead)
- User wants a new project scaffolded from scratch (use `brainstorming` skill)

---

## Workflow

### Phase 0 — Resolve Target

Determine what to scan. Ask if not specified:

```
1. Current Claude Code workspace   → use `.` (cwd)
2. Local path                      → use the provided path
3. Forgejo/Git URL                 → pass --forgejo-url to discover.py
```

If the user provides a Forgejo/Git URL, extract it and pass it directly to discover.py.
The script handles cloning automatically.

**Confirm before proceeding:**
> "Scanning `{resolved_path}` — is that the right target?"

---

### Phase 1 — Run Discovery

```bash
# Determine the skill directory (where this SKILL.md lives)
SKILL_DIR="$(dirname "$(realpath "$0")")"  # or resolve from context

# Set output dir — default to project root or a fe-output subdirectory
OUTPUT_DIR="{target_path}/fe-output"
mkdir -p "$OUTPUT_DIR"

# Run the discovery script
python "{SKILL_DIR}/scripts/discover.py" {target_path} \
    [--forgejo-url {url_if_provided}] \
    --output "$OUTPUT_DIR/context.json"
```

After running, **read context.json** and surface a concise discovery summary to the user
before proceeding:

```
📦 Project: {project_name}  ({domain})
🧩 Frameworks: {frameworks}
🗄️  Databases: {databases}
🔐 Auth: {auth_tools}
📄 Routes/Pages: {total_routes}
🧱 Components: {total_components}
🚧 Stubs/TODOs: {total_stubs}
🐍 Empty Functions: {total_empty_fns}
```

Ask: **"Does this look right? Anything to correct before I do the research phase?"**

---

### Phase 2 — Web Research

Using the detected `domain` from context.json:

1. **Load the comparables list** from `data/app_types.json` for the detected domain.
   If domain not found, fall back to `"web-app"`.

2. **Run the following searches** (use your web_search tool):
   - The 2-3 `search_queries` for the detected domain
   - For each of the top 3-4 comparable apps: `"{app_name} features 2025"`
   - `"{domain} SaaS best practices features 2025"` (or equivalent)
   - `"what features should a {domain} app have"`

3. **For each notable competitor**, fetch its features page or about page if a URL is
   readily available in search results. Use web_fetch if needed.

4. **Assemble research.json** — write it to `$OUTPUT_DIR/research.json`.
   Strict format (see schema below). This file is what generate_report.py consumes.

**research.json Schema:**
```json
{
  "domain": "sports-pool",
  "searched_at": "2026-04-20T14:30:00",
  "competitors": [
    {
      "name": "ESPN Fantasy Pick'em",
      "url": "https://fantasy.espn.com",
      "description": "One-line description of what it is.",
      "notable_features": [
        "Feature A",
        "Feature B"
      ],
      "differentiators": [
        "What makes it stand out vs. generic options"
      ]
    }
  ],
  "enhancements": [
    {
      "title": "Real-time Score Updates",
      "priority": "high",
      "effort": "medium",
      "category": "Live Data",
      "description": "Paragraph describing the enhancement in detail.",
      "rationale": "Why this matters for the specific domain/user base.",
      "implementation_notes": [
        "Use WebSockets or SSE for live push",
        "Integrate with The Odds API or ESPN API",
        "Consider fallback polling if WebSocket not supported"
      ],
      "seen_in": ["ESPN Fantasy", "Sleeper", "DraftKings"]
    }
  ]
}
```

**Priority values:** `critical`, `high`, `medium`, `low`  
**Effort values:** `small`, `medium`, `large`, `xl`

> **⚠️ Aim for 8–15 well-researched enhancements.** Quality over quantity.
> Each enhancement should be specific to THIS project's domain and detected stack,
> not generic advice.

**Tailor enhancements to the actual stack.** For example:
- If Next.js detected → suggest App Router patterns, RSC, streaming
- If Supabase detected → suggest Row Level Security, Realtime subscriptions
- If stubs detected → call out "Finish X stub feature" as a high-value quick win

---

### Phase 3 — Generate Report

```bash
python "{SKILL_DIR}/scripts/generate_report.py" \
    "$OUTPUT_DIR/context.json" \
    "$OUTPUT_DIR/research.json" \
    --output "{target_path}/FEATURE_ENHANCEMENTS.md"
```

After generating:
- Read the report file
- Present it to the user with `present_files` if available
- Give a **brief spoken summary** of the top 3 recommendations

---

### Phase 4 — Interactive Drill-Down (optional)

After delivering the report, offer:

```
What would you like to do next?

A) 🔬 Deep-dive on a specific enhancement (full implementation plan)
B) 🎯 Filter by priority or effort level
C) 🔄 Re-scan after making changes
D) 📋 Export the matrix as a Todoist task list
E) 🏗️ Scaffold the top enhancement right now
```

If the user picks **D**, format enhancements as Todoist tasks and add them via the
Todoist MCP if connected.

If the user picks **E**, use the `brainstorming` skill or `senior-frontend` skill
depending on what the top enhancement is.

---

## File Layout

```
feature-enhance/
├── SKILL.md                    ← this file
├── scripts/
│   ├── discover.py             ← Phase 1: deep codebase scanner → context.json
│   └── generate_report.py      ← Phase 3: assembles FEATURE_ENHANCEMENTS.md
└── data/
    └── app_types.json          ← domain → comparables + search queries
```

**Output files** (written to `{target}/fe-output/`):
```
fe-output/
├── context.json                ← raw discovery data
└── research.json               ← Claude-assembled competitor/enhancement data
FEATURE_ENHANCEMENTS.md         ← final report (in project root)
```

---

## Edge Cases

| Situation | How to Handle |
|-----------|--------------|
| Forgejo URL requires auth token | Ask the user for a personal access token; use `GIT_TOKEN` env or `git clone https://token@url` |
| Monorepo (multiple apps) | `discover.py` will detect multiple `package.json` files; ask user which sub-app to target |
| Very large codebase (50k+ files) | `discover.py` caps stubs at 500 and routes at 200 — mention this in the summary |
| Domain not in app_types.json | Fall back to `"web-app"` key; note the fallback to the user |
| No internet access | Skip research phase; generate report with context only and note the gap |
| `discover.py` fails (bad encoding, etc.) | Surface the error, offer to proceed with manual stack description from the user |

---

## Tips for Best Results

- **Run from inside the project root** whenever possible — this gives `discover.py` the
  cleanest signal without needing explicit path arguments.
- **For Forgejo repos**, use the full clone URL including `.git` suffix.
- **The research phase is where the real value is** — let it run a solid 4-6 web searches
  before writing research.json. Don't rush it with just 1-2 queries.
- **Stack specificity matters** — enhancements that reference the actual detected frameworks
  (Next.js App Router, Supabase Realtime, Prisma schema extensions, etc.) are far more
  actionable than generic web app advice.
- If the user's Forgejo instance is `forgejo.example.com` (or similar internal host),
  the clone may need to run with `GIT_SSL_NO_VERIFY=1` if using a self-signed cert.
