---
name: integration-mapper
version: 1.0.0
description: Maps every third-party service the project depends on with 3-dimensional risk rating (blast radius, pricing exposure, deprecation risk), fallback plans, review cadence, and staleness detection. Triggers on "map my dependencies", "audit third-party services", "what am I depending on", "integration risk review", "add a service dependency", or "review my integrations". Part of the solo-dev-suite — loads the project profile via the orchestrator. Not for internal code dependencies (use tech-debt-register) or security-specific audits (use security-audit).
---

# Integration Mapper

Maintains an authoritative map of every third-party service the project depends on, with 3-dimensional risk rating, fallback plans, and deprecation tracking. Owns `profile.third_party_services` and renders `INTEGRATIONS.md`.

## When to use this skill

- **Initial dependency mapping** — project is in architecture or early build and needs to explicitly catalog every external service it depends on.
- **Adding a new integration** — user is about to integrate a new third-party service and wants to record the dependency with risk assessment before writing code.
- **Periodic review** — user wants to check if any integrations are stale (not reviewed recently) or if risk profiles have changed.
- **Pre-launch audit** — used alongside launch-readiness to surface unhedged bets before shipping.

## When NOT to use this skill

- **No profile exists** — run the orchestrator first.
- **Internal code dependencies** — npm packages, pip packages, etc. are not "integrations" in this context. Those are tech debt territory.
- **Security-specific review** — use `security-audit` for API key exposure, CORS, rate limiting. Integration-mapper tracks the business relationship with the service, not its security posture.

## Prerequisites

- Project profile must exist: `solo-dev-suite/profiles/<slug>.json`
- Sidecar lives at: `solo-dev-suite/profiles/<slug>.integrations.json` (created on first `add`)

## Methodology — The Six Questions

For every third-party service, the mapper forces answers to six questions:

1. **What does this service do for me?** (purpose) — Forces clarity on what you'd lose if it vanished.
2. **How bad is it if this service fails for 24 hours?** (blast radius: low/medium/high/critical) — Critical means your app is dead. Low means nobody notices.
3. **How bad is it if pricing doubles next month?** (pricing exposure: low/medium/high) — High means your margins are destroyed or the service becomes unaffordable.
4. **How bad is it if the service announces deprecation in 12 months?** (deprecation risk: low/medium/high) — High means migration is painful and no clear alternatives exist.
5. **What's my fallback plan?** — Concrete alternative + estimated migration time. "We'll figure it out" is not a plan.
6. **When do I re-evaluate?** (review cadence: monthly/quarterly/never) — Critical services should be quarterly minimum.

### Risk rollup

The profile mirror's `risk_level` is the **max** of (blast_radius, pricing_exposure, deprecation_risk). A service with low blast but high deprecation risk is still a high-risk service. This gives sibling skills a single signal to consume.

### Unhedged bet detection

A service with **no fallback plan** (empty or "none") AND **high or critical blast radius** is an unhedged bet. The `list` and `render` commands surface these with warnings.

### Staleness detection

- `review_cadence: "quarterly"` + `last_reviewed` > 90 days ago = STALE
- `review_cadence: "monthly"` + `last_reviewed` > 30 days ago = STALE
- `review_cadence: "never"` = never stale (explicitly opted out)

## Operations

### 1. Add (new service)

**Goal**: Record a new third-party dependency with full risk assessment.

**Workflow**:

1. User identifies the service being added (or Claude surfaces it from conversation context).
2. Walk through the Six Questions for this service. Propose ratings based on the service type — push back on "low" ratings that seem optimistic.
3. Persist:
   ```bash
   echo '<payload>' | python scripts/integration_tool.py add <slug> --from-stdin
   ```

**Stdin shape**:
```json
{
  "reason": "Adding payment processor for v1 launch",
  "service": {
    "name": "Stripe Connect",
    "category": "payments",
    "purpose": "Payment processing with payouts to trainers",
    "blast_radius": {"rating": "critical", "rationale": "App is useless without payments"},
    "pricing_exposure": {"rating": "medium", "current_cost_usd_per_month": 0, "notes": "2.9% + $0.25 per txn"},
    "deprecation_risk": {"rating": "low", "notes": "Stripe is stable, 5+ years of API continuity"},
    "fallback": {"plan": "Migrate to LemonSqueezy; 1-2 week effort", "tested": false, "notes": ""},
    "review_cadence": "quarterly",
    "notes": ""
  }
}
```

### 2. Update (modify existing service)

```bash
echo '<payload>' | python scripts/integration_tool.py update <slug> --from-stdin
```

Payload must include `service_id` and `reason`. Only provided fields are updated — omitted fields keep their current values.

### 3. Remove (stop using a service)

```bash
python scripts/integration_tool.py remove <slug> --service-id INT01 --reason "Migrated to self-hosted alternative"
```

Removes from active services list but keeps the entry in `change_log` for audit trail.

### 4. List (show all services)

```bash
python scripts/integration_tool.py list <slug>
python scripts/integration_tool.py list <slug> --json
python scripts/integration_tool.py list <slug> --risk-min high
```

Human-readable output shows each service with risk indicators, staleness warnings, and unhedged bet flags. `--risk-min` filters to services at or above the specified risk level.

### 5. Show (single service detail)

```bash
python scripts/integration_tool.py show <slug> --service-id INT01
```

### 6. Review (mark as reviewed)

```bash
python scripts/integration_tool.py review <slug> --service-id INT01
```

Updates `last_reviewed` to now. Used during periodic reviews to clear staleness warnings.

### 7. Render

```bash
python scripts/integration_tool.py render <slug> [--output-dir <path>]
```

Generates `INTEGRATIONS.md` with risk matrix, unhedged bet warnings, staleness flags.

### 8. Delete

```bash
python scripts/integration_tool.py delete <slug> [--yes]
```

Removes the entire sidecar. Profile mirror is NOT cleared (other skills may reference it).

## Sidecar data shape

Authoritative schema: `templates/integrations.schema.json`. Top-level keys:

- `schema_version` (const 1)
- `project_slug` (kebab-case)
- `created_at` / `updated_at` (ISO timestamps)
- `services[]` — active integration records
  - `id` (e.g. "INT01"), `name`, `category`, `purpose`, `added_at`
  - `blast_radius` — `{rating, rationale}`
  - `pricing_exposure` — `{rating, current_cost_usd_per_month, notes}`
  - `deprecation_risk` — `{rating, notes}`
  - `fallback` — `{plan, tested, notes}`
  - `review_cadence`, `last_reviewed`, `notes`
- `change_log[]` — `{at, action, service_id, change, reason}`

## Profile mirror

After every sidecar write, `profile.third_party_services` is updated with the lean mirror shape:
```json
[{"name": "...", "purpose": "...", "risk_level": "high", "fallback": "..."}]
```

Also updates `last_skill_run["integration-mapper"]`.

## Output docs

`<output_dir>/INTEGRATIONS.md` — risk matrix table, per-service detail sections, unhedged bet warnings, staleness flags, change log.

## Files

```
integration-mapper/
├── SKILL.md                               # this file
├── scripts/
│   └── integration_tool.py                # add / update / remove / list / show / review / render / delete
└── templates/
    ├── integrations.schema.json           # JSON Schema for sidecar
    └── INTEGRATIONS.md.tmpl               # rendered doc template
```

## Testing

```bash
echo '{"reason":"initial capture","service":{"name":"Stripe Connect","category":"payments","purpose":"Payments","blast_radius":{"rating":"high","rationale":"x"},"pricing_exposure":{"rating":"medium","current_cost_usd_per_month":0,"notes":"x"},"deprecation_risk":{"rating":"low","notes":"x"},"fallback":{"plan":"LemonSqueezy","tested":false,"notes":""},"review_cadence":"quarterly"}}' \
  | python scripts/integration_tool.py add my-project --from-stdin

python scripts/integration_tool.py list my-project
python scripts/integration_tool.py list my-project --risk-min high
python scripts/integration_tool.py show my-project --service-id INT01
python scripts/integration_tool.py review my-project --service-id INT01
python scripts/integration_tool.py render my-project
python scripts/integration_tool.py delete my-project --yes
```

Expected: add creates sidecar + mirrors to profile, list shows risk indicators, risk filter works, review clears staleness, render produces INTEGRATIONS.md, delete cleans up.
