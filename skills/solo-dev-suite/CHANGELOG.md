# Changelog

All notable changes to the Solo Dev Suite are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-04-24

### Added
- **Marketplace structure**: `.claude-plugin/marketplace.json` and per-skill `plugin.json` files enabling `claude plugin marketplace add` installation
- **Semantic versioning**: `version` field in every SKILL.md frontmatter and children.json entry
- **Onboarding wizard** (`quickstart.py`): auto-detects project stack, type, hosting, and phase from directory contents so onboarding only asks 5-7 questions instead of 10+
- **Cross-skill dashboard** (`dashboard.py`): unified status view reading all sidecar files, with terminal, Markdown, and self-contained HTML output that auto-opens in the browser
- **Portfolio view** (`portfolio.py`): side-by-side comparison of all projects with health scores sorted by urgency
- **Handoff generator** (`handoff.py`): aggregates all skill outputs into PROJECT_HANDOFF.md with developer and buyer modes
- **This changelog**: converted from session-based format to semver-based [Keep a Changelog](https://keepachangelog.com/) format

### Fixed
- CRLF line endings in install.sh breaking direct execution on Linux (added .gitattributes with `eol=lf`)

## [1.0.0] - 2026-04-21

### Added

#### Master orchestrator (solo-dev-suite)
- Profile CRUD via `profile_io.py` (init, show, list, update, delete)
- Phase-aware skill menu via `list_skills.py`
- JSON Schema validation with inline validator
- Atomic writes, tagged stderr, standardized exit codes

#### mvp-scope-guardian
- 4-bucket scoping model: LAUNCH-BLOCKING / POST-LAUNCH V1.1 / PARKING LOT / WON'T BUILD
- Effort/impact scoring, scope creep detection with recorded-NO rationale
- Commands: lock, show, list, creep-check, rescope, render, delete

#### saas-pricing-architect
- Versioned pricing with competitive anchoring enforced (min 2 competitors)
- Strategy types: paid-only, free-trial, freemium
- Profile mirror: `pricing_model` with active tier summary
- Commands: design, show, iterate, render, delete

#### launch-readiness
- 9-category tailored checklist (auth, error handling, legal, payment, email, performance, SEO, mobile, monitoring)
- Blocker-gated sign-off; tailored by project_type, business_model, pricing_model, third_party_services
- Commands: init, show, check, sign-off, render, delete

#### integration-mapper
- 3D risk rating: blast radius, pricing exposure, deprecation risk
- Unhedged bet detection (no fallback + high/critical blast), staleness warnings
- Profile mirror: `third_party_services` lean array
- Commands: add, update, remove, list, show, review, render, delete

#### adr-generator
- Michael Nygard format with sequential numbering (0001, 0002...)
- Status lifecycle: proposed -> accepted -> superseded/deprecated
- Bidirectional supersession tracking
- Commands: new, show, list, supersede, status, render, delete

#### security-audit
- 10-category tailored checklist with severity levels (critical/high/medium/low)
- Stack-aware: keyword matching on primary_stack + per-service items from third_party_services
- Accepted-risk requires rationale; sign-off gated on criticals+highs resolved
- Commands: init, show, list, check, accept-risk, sign-off, render, delete

#### auto-docs
- 4 generated doc types: README.md, SETUP.md, ARCHITECTURE.md, CHANGELOG.md
- Pulls from profile + sibling sidecars; conditional section inclusion
- Preserved regions survive regeneration via HTML comment markers
- Commands: init, generate, release, update-content, show, delete

#### tech-debt-register
- 9 categories, impact/effort/urgency scoring
- Priority recommendation engine: score = (impact * urgency) / effort
- Status lifecycle: open -> paid-down/accepted, with reopen
- Commands: log, list, show, resolve, accept, reopen, render, delete

#### testing-strategy
- 4 testing categories: unit, integration, e2e, manual
- Effort splits, explicit skips with rationale, CI gates
- Review cadence with staleness detection
- Commands: design, show, iterate, review, render, delete

#### sprint-planner
- Honest capacity math with configurable buffer for real life
- Velocity tracking from actual completed sprint hours
- Launch countdown: red/yellow/green signal against launch_target_date
- Incomplete items return to backlog with priority bumped to "high"
- Capacity guard: warns if planned hours exceed 120% of effective capacity
- Commands: init, add, plan, start, update, complete, show, render, delete

#### Cross-skill integration
- Full end-to-end integration: pricing -> launch-readiness, integrations -> security-audit
- Profile mirrors populated and flowing correctly across all skills
