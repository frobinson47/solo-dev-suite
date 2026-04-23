# Solo Dev Suite

A collection of Claude skills covering the full solo-developer lifecycle -- from locked scope through long-term sustainment -- that share a **central project profile** so you never re-establish context.

## Skills (10 active)

| Skill | Phase(s) | Status | What it does |
|-------|----------|--------|-------------|
| **mvp-scope-guardian** | scope | active | 4-bucket scope lock + creep detection |
| **saas-pricing-architect** | scope, grow | active | Versioned pricing with competitive anchoring |
| **integration-mapper** | architecture, build | active | 3rd-party dependency risk audit with 3D scoring |
| **adr-generator** | architecture, build | active | Architecture Decision Records (Nygard format) |
| **tech-debt-register** | build, sustain | active | Managed debt backlog with priority-ranked pay-downs |
| **testing-strategy** | build | active | Right-sized test plan (unit/integration/e2e/manual) |
| **launch-readiness** | ship | active | Pre-ship gate with tailored checklist |
| **security-audit** | ship | active | Stack-aware security pass with 10 categories |
| **auto-docs** | ship, sustain | active | Generated README, SETUP, ARCHITECTURE, CHANGELOG |
| **sprint-planner** | build | active | Solo-dev sprints with honest capacity math + velocity tracking |

## How it works

```
solo-dev-suite/
  profiles/<slug>.json          # Central project profile
  profiles/<slug>.pricing.json  # Sidecar owned by saas-pricing-architect
  profiles/<slug>.scope.json    # Sidecar owned by mvp-scope-guardian
  profiles/<slug>.*.json        # Each skill owns its sidecar
  data/children.json            # Skill registry
  scripts/profile_io.py         # Profile CRUD
  scripts/list_skills.py        # Phase-aware skill menu
```

1. **Create a profile**: `echo '{...}' | python scripts/profile_io.py init --from-stdin`
2. **See available skills**: `python scripts/list_skills.py --slug <slug>` (filtered by current phase)
3. **Run a skill**: Each skill has its own CLI in `<skill>/scripts/<tool>.py`
4. **Cross-skill data flows**: Skills write lean mirrors to the profile so other skills can read cheaply. Example: `integration-mapper` writes `profile.third_party_services`, which `launch-readiness` and `security-audit` read to tailor their checklists.

## File structure per child skill

```
<skill-name>/
  SKILL.md                      # Claude's playbook
  scripts/<tool>_tool.py        # CLI with subcommands
  templates/<skill>.schema.json # JSON Schema for the sidecar
  templates/*.md.tmpl           # Rendered doc template(s)
```

## Architecture principles

- **Zero external dependencies**: Pure Python stdlib everywhere. No pip installs needed.
- **Self-contained skills**: Each skill duplicates its validator/utilities. No shared library.
- **Atomic writes**: Write to `.tmp` then rename. No mid-write corruption.
- **Profile mirrors**: Skills write lean summaries to the profile for cross-skill reads.
- **Sidecars for data**: Each skill owns `<slug>.<skill>.json`. Never writes to another skill's sidecar.

## Quick start

```bash
cd solo-dev-suite

# Create a project profile
echo '{
  "project_name": "My SaaS",
  "project_slug": "my-saas",
  "description": "What this project does",
  "project_type": "saas",
  "primary_stack": ["React", "FastAPI", "PostgreSQL"],
  "hosting": "homelab",
  "target_users": "Who uses this",
  "business_model": "saas-subscription",
  "available_hours_per_week": 15,
  "current_phase": "scope"
}' | python scripts/profile_io.py init --from-stdin

# See what skills are relevant for the current phase
python scripts/list_skills.py --slug my-saas

# Run any skill
cd ../mvp-scope-guardian
echo '{...}' | python scripts/scope_tool.py lock my-saas --from-stdin
```

See [GETTING_STARTED.md](docs/GETTING_STARTED.md) for a full onboarding walkthrough.

## Schema migrations

The profile schema is versioned via `schema_version` (currently `1`). To introduce a breaking change:

1. Bump `schema_version` in `templates/profile.schema.json`.
2. Bump the matching constant in `profile_io.py`.
3. Add a migration function that upgrades old profiles to the new shape.
4. Wire the migration into `_read_profile` so old files auto-upgrade on load.

## Skill lifecycle

Skills are tracked in `data/children.json`. Each records its last run in `profile.last_skill_run.<skill>` so the orchestrator can flag stale work.

To add a new skill: create the folder, add an entry to `children.json` with `status: "active"`, and the orchestrator picks it up on the next `list_skills.py` call.
