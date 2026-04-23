# Solo Dev Suite

A collection of **Claude Code skills and plugins** covering the full solo-developer lifecycle -- from scope lock through long-term sustainment. All skills share a **central project profile** so you never re-establish context between runs.

## What's Included

### Skills (13)

| Skill | Phase(s) | What it does |
|-------|----------|-------------|
| **solo-dev-suite** | all | Master orchestrator -- loads profiles, routes to child skills |
| **mvp-scope-guardian** | scope | 4-bucket scope lock + creep detection |
| **saas-pricing-architect** | scope, grow | Versioned pricing with competitive anchoring |
| **integration-mapper** | architecture, build | 3rd-party dependency risk audit with 3D scoring |
| **adr-generator** | architecture, build | Architecture Decision Records (Nygard format) |
| **sprint-planner** | build | Solo-dev sprints with honest capacity math + velocity tracking |
| **tech-debt-register** | build, sustain | Managed debt backlog with priority-ranked pay-downs |
| **testing-strategy** | build | Right-sized test plan (unit/integration/e2e/manual) |
| **launch-readiness** | ship | Pre-ship gate with tailored 9-category checklist |
| **security-audit** | ship | Stack-aware security pass with 10 categories |
| **auto-docs** | ship, sustain | Generated README, SETUP, ARCHITECTURE, CHANGELOG |
| **design-loop** | any | Iterative design exploration loop |
| **feature-enhance** | any | Feature enhancement discovery and analysis |

### Plugins (2)

| Plugin | What it does |
|--------|-------------|
| **market-feasibility** | 7-dimension feasibility study with GO/NO-GO verdict |
| **software-valuation** | Pricing strategy analysis from local code or public repo |

## Lifecycle Phases

Skills map to a left-to-right lifecycle:

```
idea -> scope -> architecture -> build -> ship -> grow -> sustain
```

The orchestrator filters skills by your project's current phase so you only see what's relevant.

## Install

### Linux / macOS

```bash
git clone https://github.com/frobinson47/solo-dev-suite.git
cd solo-dev-suite
./install.sh
```

### Windows (PowerShell)

```powershell
git clone https://github.com/frobinson47/solo-dev-suite.git
cd solo-dev-suite
.\install.ps1
```

The installer symlinks (Linux/macOS) or copies (Windows) skills into `~/.claude/skills/` and plugins into `~/.claude/plugins/marketplaces/`. Restart Claude Code after installing.

## Quick Start

1. **Install** (see above)
2. **Create a project profile** -- copy `skills/solo-dev-suite/profiles/example.json`, rename it to `<your-slug>.json`, and fill in your project details
3. **Ask Claude Code** -- "set up my-project in the suite" or invoke any skill directly (e.g., "run a security audit on my-project")

The orchestrator loads your profile automatically and routes to the right skill.

## How It Works

```
solo-dev-suite/
  skills/
    solo-dev-suite/           # Master orchestrator
      profiles/<slug>.json    # Your project profiles (gitignored)
      profiles/example.json   # Template to copy
      data/children.json      # Skill registry
      scripts/profile_io.py   # Profile CRUD
      scripts/list_skills.py  # Phase-aware skill menu
    mvp-scope-guardian/       # Child skill
    saas-pricing-architect/   # Child skill
    ...                       # (11 more)
  plugins/
    market-feasibility/       # Pre-project feasibility plugin
    software-valuation/       # Pre-project valuation plugin
```

- **Zero external dependencies** -- pure Python stdlib. No pip installs.
- **Self-contained skills** -- each skill has its own scripts and templates.
- **Atomic writes** -- write to `.tmp` then rename. No mid-write corruption.
- **Cross-skill data flows** -- skills write lean summaries to the profile so other skills can read them. Example: `integration-mapper` populates `third_party_services`, which `security-audit` reads to tailor its checklist.

## Updating

```bash
cd solo-dev-suite
git pull
./install.sh   # or .\install.ps1 on Windows
```

## Requirements

- **Claude Code** (CLI, desktop app, or IDE extension)
- **Python 3.9+** (stdlib only)

## License

MIT
