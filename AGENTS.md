# Solo Dev Suite — Agent Integration Guide

This document tells any AI coding agent how to discover, invoke, and integrate with the Solo Dev Suite. It is agent-agnostic — the same Python scripts work with Claude Code, Cursor, Codex, Gemini CLI, Aider, Continue, or any agent that can run shell commands.

## Prerequisites

- Python 3.9+
- No pip installs needed — all scripts use pure stdlib

## Quick Start

```bash
# 1. Detect project stack and pre-fill profile fields
python skills/solo-dev-suite/scripts/quickstart.py detect /path/to/project

# 2. Create a profile (pipe detected + manual fields as JSON)
echo '{"project_name":"My App","project_slug":"my-app",...}' | \
  python skills/solo-dev-suite/scripts/profile_io.py init --from-stdin

# 3. See available skills for current phase
python skills/solo-dev-suite/scripts/list_skills.py --slug my-app

# 4. Run a skill
python skills/<skill-name>/scripts/<tool>.py <command> my-app

# 5. View unified dashboard
python skills/solo-dev-suite/scripts/dashboard.py status my-app
```

## Architecture

```
solo-dev-suite/
├── skills/
│   ├── solo-dev-suite/          # Orchestrator + shared infrastructure
│   │   ├── profiles/            # Project profiles + sidecar data
│   │   │   ├── <slug>.json                  # Main profile
│   │   │   ├── <slug>.scope.json            # Scope guardian output
│   │   │   ├── <slug>.pricing.json          # Pricing architect output
│   │   │   ├── <slug>.security.json         # Security audit output
│   │   │   ├── <slug>.readiness.json        # Launch readiness output
│   │   │   ├── <slug>.sprint.json           # Sprint planner output
│   │   │   ├── <slug>.techdebt.json         # Tech debt register output
│   │   │   ├── <slug>.integrations.json     # Integration mapper output
│   │   │   ├── <slug>.testing.json          # Testing strategy output
│   │   │   ├── <slug>.adr.json              # ADR generator output
│   │   │   ├── <slug>.docs.json             # Auto-docs output
│   │   │   └── <slug>.exported.json         # Issue export tracking
│   │   ├── scripts/             # Orchestrator scripts
│   │   └── data/
│   │       └── children.json    # Skill registry (phases, deps, triggers)
│   ├── adr-generator/           # Architecture Decision Records
│   ├── auto-docs/               # Documentation generator
│   ├── integration-mapper/      # Third-party service mapping
│   ├── launch-readiness/        # Pre-ship gate checklist
│   ├── mvp-scope-guardian/      # Feature scoping + scope creep detection
│   ├── saas-pricing-architect/  # Pricing strategy + tier design
│   ├── security-audit/          # 10-category security checklist
│   ├── sprint-planner/          # Solo-dev sprint planning
│   ├── tech-debt-register/      # Tech debt tracking + prioritization
│   └── testing-strategy/        # Right-sized testing plan
└── plugins/
    ├── market-feasibility/      # Market feasibility study
    └── software-valuation/      # Software valuation + pricing
```

## Skill Registry

The canonical skill list lives in `skills/solo-dev-suite/data/children.json`. Each entry contains:

| Field | Purpose |
|-------|---------|
| `name` | Skill identifier (kebab-case) |
| `version` | Semantic version |
| `status` | `active`, `planned`, or `deprecated` |
| `phases` | Which project phases this skill applies to |
| `depends_on` | Skills that should run before this one |
| `enhances` | Skills that benefit from this one's output |
| `triggers` | Natural-language phrases that should invoke this skill |
| `output_location` | Where this skill writes its data |

To query the registry programmatically:

```bash
# List all skills
python skills/solo-dev-suite/scripts/list_skills.py --json

# Filter by phase
python skills/solo-dev-suite/scripts/list_skills.py --phase build --json

# Check dependencies before running a skill
python skills/solo-dev-suite/scripts/list_skills.py --check security-audit --slug my-app
```

## Script Conventions

Every script in the suite follows these patterns:

| Pattern | Detail |
|---------|--------|
| CLI framework | `argparse` with subparsers |
| Entry point | `main(argv=None)` for testability |
| Output | Human-readable by default, `--json` for machine-readable |
| Errors | Tagged stderr via `_err()` helper |
| Exit codes | 0=success, 1=not found, 2=broken install, 3+=skill-specific |
| File writes | Atomic via `.tmp` + `.replace()` |
| Encoding | UTF-8 everywhere |
| Dependencies | Zero — pure Python stdlib |

## Orchestrator Scripts

| Script | Purpose | Key Commands |
|--------|---------|--------------|
| `profile_io.py` | Profile CRUD | `init`, `show`, `list`, `update`, `delete` |
| `list_skills.py` | Phase-aware skill menu | `--phase`, `--slug`, `--check` |
| `quickstart.py` | Project auto-detection | `detect <path>` |
| `dashboard.py` | Cross-skill status view | `status <slug>`, `render <slug>` |
| `portfolio.py` | Multi-project comparison | `view`, `health <slug>` |
| `handoff.py` | Handoff document generator | `generate <slug>` |
| `export_issues.py` | Issue tracker export | `export <slug>`, `status <slug>` |
| `create_skill.py` | Scaffold new skills | `new <name>` |

## Child Skill Scripts

| Skill | Script | Key Commands |
|-------|--------|--------------|
| adr-generator | `adr_tool.py` | `new`, `list`, `show`, `update`, `render` |
| auto-docs | `docs_tool.py` | `init`, `generate`, `show` |
| integration-mapper | `integration_tool.py` | `init`, `add`, `show`, `render` |
| launch-readiness | `readiness_tool.py` | `init`, `check`, `show`, `render` |
| mvp-scope-guardian | `scope_tool.py` | `init`, `add`, `show`, `render`, `creep-check` |
| saas-pricing-architect | `pricing_tool.py` | `init`, `show`, `render` |
| security-audit | `security_tool.py` | `init`, `check`, `show`, `render` |
| sprint-planner | `sprint_tool.py` | `init`, `plan`, `show`, `render` |
| tech-debt-register | `debt_tool.py` | `init`, `add`, `show`, `render` |
| testing-strategy | `testing_tool.py` | `init`, `show`, `render` |

## Data Flow

All inter-skill communication happens through JSON files, not in-memory state:

```
Profile (slug.json)
    │
    ├── Scope Guardian writes → slug.scope.json
    ├── Pricing Architect writes → slug.pricing.json
    ├── Sprint Planner reads scope, writes → slug.sprint.json
    ├── Security Audit writes → slug.security.json
    ├── Launch Readiness reads security + integrations, writes → slug.readiness.json
    ├── Integration Mapper writes → slug.integrations.json
    ├── Testing Strategy writes → slug.testing.json
    ├── Tech Debt Register writes → slug.techdebt.json
    ├── ADR Generator writes → slug.adr.json
    └── Auto-Docs reads all sidecars, writes → slug.docs.json
```

## Dependency Graph

Some skills should run before others:

- `mvp-scope-guardian` **enhances** `sprint-planner` (scope informs sprint backlog)
- `security-audit` **enhances** `launch-readiness` (security findings feed readiness gate)
- `integration-mapper` **enhances** `security-audit`, `launch-readiness`
- `saas-pricing-architect` **enhances** `launch-readiness`
- `testing-strategy` **enhances** `launch-readiness`
- `launch-readiness` **depends on** `security-audit` (hard dependency — won't pass without it)
- `sprint-planner` **depends on** `mvp-scope-guardian` (hard dependency)

Check dependencies before running:

```bash
python skills/solo-dev-suite/scripts/list_skills.py --check launch-readiness --slug my-app
```

## Integration Patterns

### Cursor

Place `.cursorrules` in the project root (included in this repo). Cursor reads it automatically.

### Codex / OpenAI

Use the `codex.md` file (included in this repo) as a system prompt or task definition. It provides Codex with the skill invocation patterns.

### Gemini CLI

Gemini CLI reads `AGENTS.md` (this file) from the project root. No additional configuration needed.

### Aider / Continue / Other

Any agent that can:
1. Read this file for context
2. Execute `python` commands
3. Read/write JSON files

...can use the full suite. The scripts are the API.

## Adding New Skills

```bash
python skills/solo-dev-suite/scripts/create_skill.py new my-skill \
    --description "What this skill does" \
    --phases "build,ship"
```

This creates the skill directory, registers it in `children.json` and `marketplace.json`, and generates starter files following all suite conventions.
