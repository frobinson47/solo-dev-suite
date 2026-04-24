---
name: launch-readiness
version: 1.0.0
description: Pre-ship gate that produces a tailored launch checklist covering auth, error handling, legal, payment flow, email deliverability, performance, SEO, mobile, and monitoring — with severity-gated sign-off. Triggers on "launch readiness", "pre-ship check", "am I ready to launch", "go-live checklist", or "what's blocking launch". Part of the solo-dev-suite — loads the project profile via the orchestrator. Not for security audits (use security-audit) or documentation generation (use auto-docs).
---

# Launch Readiness

Produces a **tailored pre-ship checklist** gated on blocker resolution. The checklist is dynamically assembled based on the project's type, business model, pricing strategy, and third-party dependencies — so a marketing site doesn't get payment-flow items, and a freemium SaaS gets free-tier enforcement checks.

## When to use this skill

- **First launch gate** — project is approaching ship date and needs a structured "are we actually ready?" pass.
- **Re-verification** — something significant changed post-sign-off (new integration, pricing pivot, auth overhaul) and the checklist needs a fresh cycle.
- **Progress tracking** — user wants to chip away at readiness items over multiple sessions, marking items as they verify each one.

## When NOT to use this skill

- **No profile exists** — run the orchestrator first. This skill requires `profiles/<slug>.json`.
- **Security-specific deep dive** — use `security-audit`. Launch-readiness covers auth basics; security-audit goes deeper (RLS, CORS, rate limiting, secret rotation).
- **Documentation generation** — use `auto-docs`. Launch-readiness checks that docs *exist*; auto-docs *creates* them.
- **The project isn't close to shipping** — this skill is for the "ship" phase. Running it during early build creates noise.

## Prerequisites

- Project profile must exist: `solo-dev-suite/profiles/<slug>.json`
- Sidecar readiness file lives at: `solo-dev-suite/profiles/<slug>.readiness.json` (created by this skill on `init`)
- For best tailoring, the profile should have `project_type`, `business_model`, and optionally `pricing_model` and `third_party_services` populated.

## Methodology — The Nine Categories

The checklist covers nine categories that represent real post-launch pain points for solo devs. Each category contains items with severity levels:

- **blocker** — MUST be `passed` before sign-off. These are the things that make you look unprofessional, lose money, or break trust on day one.
- **high** — should be done for launch but won't hard-block sign-off.
- **medium** — nice-to-have for launch day, fine to do in week 1.
- **low** — polish items. Do them when you can.

### The Nine Categories

1. **Auth & session security** (`auth`) — Password reset works, sessions expire, logout works, email verification if applicable.
2. **Error handling** (`error`) — No raw stack traces, 404/500 pages exist, form errors surface nicely.
3. **Legal** (`legal`) — ToS, Privacy Policy, cookie consent (EU), age-gate if applicable.
4. **Payment flow** (`payment`) — Successful purchase, failed card, cancel flow, refund path, webhook idempotency, tax handling.
5. **Email deliverability** (`email`) — Transactional emails arrive, DKIM/SPF/DMARC set, unsubscribe link in marketing emails.
6. **Performance baseline** (`perf`) — Homepage < 3s on 3G, critical path works on slow connections, images optimized.
7. **SEO & metadata** (`seo`) — Page titles, meta descriptions, OG tags, robots.txt, sitemap.xml, canonical URLs.
8. **Mobile** (`mobile`) — Layout at 375px, 44px+ tap targets, no horizontal scroll.
9. **Monitoring** (`monitoring`) — Error tracking wired, uptime check pinging, log rotation or aggregation.

### Tailoring Rules

Categories and items are dynamically included/excluded based on profile data:

- `business_model in ["free-self-hosted", "internal-only"]` → drop payment category, reduce legal items.
- `project_type == "marketing-site"` → drop auth category, reduce email to "contact form works."
- `project_type == "mobile-app"` → add app-store items (privacy manifest, screenshots, content rating).
- `pricing_model.strategy == "freemium"` → add "free tier limits enforced" and "upgrade CTA visible at limit."
- `third_party_services` contains Stripe Connect → add onboarding flow, payout timing items.

## Operations

### 1. Init (create tailored checklist)

**Goal**: Build the checklist tailored to this project and persist it.

**Workflow**:

1. Load the profile:
   ```bash
   python <SUITE_DIR>/scripts/profile_io.py show <slug> --json
   ```
2. If a readiness sidecar already exists and user didn't pass `--force`, STOP — tell the user to use `check` to update items or `delete` + re-init for a fresh cycle.
3. Run the tailoring logic against the profile to assemble the category/item list.
4. If `--from-stdin` is provided, merge any custom items or severity overrides from the stdin payload into the tailored list.
5. Persist:
   ```bash
   python scripts/readiness_tool.py init <slug>
   # or with custom overrides:
   echo '<overrides_json>' | python scripts/readiness_tool.py init <slug> --from-stdin
   ```

**Stdin override shape** (optional):
```json
{
  "target_launch_date": "2026-09-01",
  "custom_items": [
    {"category": "auth", "name": "SSO via Google works", "severity": "high"}
  ],
  "severity_overrides": {
    "AUTH01": "high"
  }
}
```

The `target_launch_date` defaults to `profile.launch_target_date` if not provided.

### 2. Show

Display current readiness state in human-readable form, or as JSON for programmatic access.

```bash
python scripts/readiness_tool.py show <slug>
python scripts/readiness_tool.py show <slug> --json
python scripts/readiness_tool.py show <slug> --category auth
```

The human-readable view shows a summary header (blockers passed/total, days to launch) followed by each category with item status indicators.

### 3. Check (mark an item)

**Goal**: Record a pass/fail/not-applicable verdict on a specific checklist item.

**Workflow**:

1. User identifies which item they're verifying (by ID like `AUTH01`).
2. Persist the status change:
   ```bash
   python scripts/readiness_tool.py check <slug> --item AUTH01 --status passed --notes "Tested with gmail+signup"
   ```
3. If the status is the same as the current status, no history entry is recorded (avoids log noise).
4. If the status changed, a history entry is appended.
5. Profile mirror is updated with new blocker counts.

**Valid statuses**: `passed`, `failed`, `not-applicable`, `not-checked` (reset).

### 4. Sign-off

**Goal**: Gate the "we are shipping" decision on blocker resolution.

```bash
python scripts/readiness_tool.py sign-off <slug> --signed-by "Developer"
```

**Behavior**:
- If ANY `severity=blocker` item has status != `passed` and != `not-applicable`, sign-off FAILS with a clear list of unresolved blockers.
- `--force` bypasses the gate (because Design Principle #10 — opinionated, not prescriptive). But it prints a loud warning about which blockers are being overridden.
- On success, `sign_off.signed_at` and `sign_off.signed_by` are stamped. `sign_off.blockers_resolved = true`.

### 5. Render

Re-generate `LAUNCH_READINESS.md` from the sidecar JSON.

```bash
python scripts/readiness_tool.py render <slug> [--output-dir <path>]
```

Default output: `<repo>/docs/` if `repository_path` is reachable, else staging dir.

### 6. Delete

Remove the sidecar and any staged docs.

```bash
python scripts/readiness_tool.py delete <slug> --yes
```

Without `--yes`, exits with a confirmation prompt message (exit code 9).

## Sidecar data shape

Authoritative schema: `templates/readiness.schema.json`. Top-level keys:

- `schema_version` (integer, const 1)
- `project_slug` (kebab-case, matches profile)
- `created_at` / `updated_at` (ISO timestamps)
- `target_launch_date` (date string, YYYY-MM-DD)
- `categories[]` — ordered list of category objects
  - `id` (string, e.g. "auth", "payment")
  - `name` (string, human-readable)
  - `applicable` (boolean — false means category was dropped by tailoring)
  - `items[]` — ordered checklist items
    - `id` (string, e.g. "AUTH01", "PAY03")
    - `name` (string, what to verify)
    - `severity` (enum: "blocker", "high", "medium", "low")
    - `status` (enum: "not-checked", "passed", "failed", "not-applicable")
    - `notes` (string, optional context from the user)
    - `checked_at` (ISO timestamp or null)
- `sign_off` — sign-off state
  - `blockers_resolved` (boolean)
  - `signed_at` (ISO timestamp or null)
  - `signed_by` (string or null)
- `history[]` — status transition log
  - `at` (ISO timestamp)
  - `item_id` (string)
  - `old_status` (string)
  - `new_status` (string)
  - `notes` (string)

## Profile mirror

After any sidecar write, `profile.readiness_model` is updated:

```json
{
  "last_check_at": "2026-08-15T10:30:00",
  "target_launch_date": "2026-09-01",
  "blockers_total": 8,
  "blockers_passed": 6,
  "blockers_remaining": 2,
  "is_shippable": false
}
```

`is_shippable` is true only when `blockers_remaining == 0` OR sign-off was forced.

## Output docs

Generated at `<output_dir>/LAUNCH_READINESS.md`:

- Header with project name, target launch date, blocker summary (X/Y passed)
- Each applicable category as a section with items in a table (ID, item, severity, status, notes)
- Status indicators: `passed`, `failed`, `not-applicable`, `not-checked`
- Sign-off block at bottom (empty until sign-off succeeds)
- History section showing recent status transitions
- Regeneration footer

## Files

```
launch-readiness/
├── SKILL.md                              # this file
├── scripts/
│   └── readiness_tool.py                 # init / show / check / sign-off / render / delete
└── templates/
    ├── readiness.schema.json             # JSON Schema for sidecar
    └── LAUNCH_READINESS.md.tmpl          # rendered checklist doc
```

## Testing

After changes to `readiness_tool.py` or any template, run the smoke sequence:

```bash
# Assumes a profile exists (e.g. my-project with project_type=saas, business_model=saas-subscription)
python scripts/readiness_tool.py init my-project
python scripts/readiness_tool.py show my-project
python scripts/readiness_tool.py show my-project --json
python scripts/readiness_tool.py show my-project --category auth
python scripts/readiness_tool.py check my-project --item AUTH01 --status passed --notes "Tested end-to-end"
python scripts/readiness_tool.py check my-project --item PAY01 --status failed --notes "Webhook sig missing"
python scripts/readiness_tool.py sign-off my-project --signed-by "Developer"   # should FAIL
python scripts/readiness_tool.py render my-project
python scripts/readiness_tool.py delete my-project --yes
```

Expected:
- `init` builds a tailored checklist (SaaS gets payment + auth; all 9 categories present for my-project).
- `show` renders a readable summary with status indicators.
- `check` updates the item status and records history.
- `sign-off` fails with "N blockers still not passed" listing the specific items.
- `render` produces `LAUNCH_READINESS.md` with the gated checklist.
- `delete` removes the sidecar cleanly.
