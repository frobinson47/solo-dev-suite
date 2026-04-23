# Changelog -- Solo Dev Suite

## v1.0.0 (2026-04-21)

Initial release. 10 active child skills + master orchestrator.

### Master orchestrator (Session 1)
- Profile CRUD via `profile_io.py` (init, show, list, update, delete)
- Phase-aware skill menu via `list_skills.py`
- JSON Schema validation with inline validator
- Atomic writes, tagged stderr, standardized exit codes

### mvp-scope-guardian (Session 2)
- 4-bucket scoping model: LAUNCH-BLOCKING / POST-LAUNCH V1.1 / PARKING LOT / WON'T BUILD
- Effort/impact scoring, scope creep detection with recorded-NO rationale
- Commands: lock, show, list, creep-check, rescope, render, delete

### saas-pricing-architect (Session 3)
- Versioned pricing with competitive anchoring enforced (min 2 competitors)
- Strategy types: paid-only, free-trial, freemium
- Profile mirror: `pricing_model` with active tier summary
- Commands: design, show, iterate, render, delete

### launch-readiness (Session 4)
- 9-category tailored checklist (auth, error handling, legal, payment, email, performance, SEO, mobile, monitoring)
- Blocker-gated sign-off; tailored by project_type, business_model, pricing_model, third_party_services
- Commands: init, show, check, sign-off, render, delete

### integration-mapper (Session 5)
- 3D risk rating: blast radius, pricing exposure, deprecation risk
- Unhedged bet detection (no fallback + high/critical blast), staleness warnings
- Profile mirror: `third_party_services` lean array
- Commands: add, update, remove, list, show, review, render, delete

### adr-generator (Session 6)
- Michael Nygard format with sequential numbering (0001, 0002...)
- Status lifecycle: proposed -> accepted -> superseded/deprecated
- Bidirectional supersession tracking
- Commands: new, show, list, supersede, status, render, delete

### security-audit (Session 7)
- 10-category tailored checklist with severity levels (critical/high/medium/low)
- Stack-aware: keyword matching on primary_stack + per-service items from third_party_services
- Accepted-risk requires rationale; sign-off gated on criticals+highs resolved
- Commands: init, show, list, check, accept-risk, sign-off, render, delete

### auto-docs (Session 8)
- 4 generated doc types: README.md, SETUP.md, ARCHITECTURE.md, CHANGELOG.md
- Pulls from profile + sibling sidecars; conditional section inclusion
- Preserved regions survive regeneration via HTML comment markers
- Commands: init, generate, release, update-content, show, delete

### tech-debt-register (Session 9)
- 9 categories, impact/effort/urgency scoring
- Priority recommendation engine: score = (impact * urgency) / effort
- Status lifecycle: open -> paid-down/accepted, with reopen
- Commands: log, list, show, resolve, accept, reopen, render, delete

### testing-strategy (Session 10)
- 4 testing categories: unit, integration, e2e, manual
- Effort splits, explicit skips with rationale, CI gates
- Review cadence with staleness detection
- Commands: design, show, iterate, review, render, delete

### sprint-planner (post-Session 11)
- Honest capacity math with configurable buffer for real life
- Velocity tracking from actual completed sprint hours
- Launch countdown: red/yellow/green signal against launch_target_date
- Incomplete items return to backlog with priority bumped to "high"
- Capacity guard: warns if planned hours exceed 120% of effective capacity
- Commands: init, add, plan, start, update, complete, show, render, delete

### Wire-up pass (Session 11)
- Full end-to-end integration test on my-project
- Cross-skill reads verified: pricing -> launch-readiness, integrations -> security-audit
- Profile mirrors populated and flowing correctly across all skills
- README, CHANGELOG, and GETTING_STARTED docs created
