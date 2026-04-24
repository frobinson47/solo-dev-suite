# Solo Dev Suite — Codex Instructions

You have access to the Solo Dev Suite, a collection of lifecycle skills for solo developers. All skills are invoked via Python scripts in the `skills/` directory. No pip installs needed — pure stdlib.

## How to use

1. **Detect a project**: `python skills/solo-dev-suite/scripts/quickstart.py detect <path>`
2. **Create a profile**: Pipe JSON to `python skills/solo-dev-suite/scripts/profile_io.py init --from-stdin`
3. **List available skills**: `python skills/solo-dev-suite/scripts/list_skills.py --slug <slug>`
4. **Run a skill**: `python skills/<skill>/scripts/<tool>.py <command> <slug>`
5. **View dashboard**: `python skills/solo-dev-suite/scripts/dashboard.py status <slug>`

## Available skills

| When the user asks about... | Run this |
|---|---|
| MVP scope, features, prioritization | `skills/mvp-scope-guardian/scripts/scope_tool.py` |
| Pricing, tiers, monetization | `skills/saas-pricing-architect/scripts/pricing_tool.py` |
| Architecture decisions, ADRs | `skills/adr-generator/scripts/adr_tool.py` |
| Third-party dependencies, integrations | `skills/integration-mapper/scripts/integration_tool.py` |
| Sprint planning, velocity, tasks | `skills/sprint-planner/scripts/sprint_tool.py` |
| Tech debt tracking | `skills/tech-debt-register/scripts/debt_tool.py` |
| Testing strategy, coverage | `skills/testing-strategy/scripts/testing_tool.py` |
| Security review, vulnerabilities | `skills/security-audit/scripts/security_tool.py` |
| Launch readiness, go-live checklist | `skills/launch-readiness/scripts/readiness_tool.py` |
| Documentation, README, changelog | `skills/auto-docs/scripts/docs_tool.py` |
| Project status across all skills | `skills/solo-dev-suite/scripts/dashboard.py` |
| Compare multiple projects | `skills/solo-dev-suite/scripts/portfolio.py` |
| Export to issue trackers | `skills/solo-dev-suite/scripts/export_issues.py` |

## Conventions

- Every script supports `--help` for usage
- Every script supports `--json` for machine-readable output
- Profiles live at `skills/solo-dev-suite/profiles/<slug>.json`
- Skill data lives in sidecar files: `profiles/<slug>.<skill>.json`
- Exit codes: 0=success, 1=not found, 2=broken install

## Full details

See `AGENTS.md` for complete architecture, data flow, and dependency graph.
