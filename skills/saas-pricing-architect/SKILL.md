---
name: saas-pricing-architect
version: 1.0.0
description: Designs a defensible SaaS pricing structure -- strategy (freemium/trial/paid), billing unit, tier count and content, psychological pricing, annual discounting, and launch vs steady-state pricing. Produces a versioned pricing model with change history and a rendered PRICING.md doc. Triggers on "design my pricing", "pricing strategy", "what should I charge", "tier structure", "iterate my pricing", "compare pricing", "am I pricing wrong". Part of the solo-dev-suite. Not for one-off "what's a fair price for X" questions (just answer those) or for non-SaaS monetization (ads, one-time sales, marketplaces).
---

# SaaS Pricing Architect

Designs and iterates on SaaS pricing with version history. Reads the project profile to anchor proposals, produces `profile.pricing_model` as the canonical active pricing, and renders `PRICING.md` as a developer reference.

## When to use this skill

- User wants to design pricing for the first time (pre-launch scoping OR mid-build before wiring Stripe tier logic).
- User wants to iterate on existing pricing based on customer feedback, churn data, or competitive moves.
- User is wiring payment logic and needs a single source of truth to code against.
- Another suite skill (launch-readiness, sprint-planner) needs to confirm pricing is locked.

## When NOT to use this skill

- **Non-SaaS monetization** -- ads, marketplace take-rates, one-time license sales, donation models. Different methodology entirely.
- **B2B enterprise contracts with custom quotes** -- this skill is for self-serve / low-touch SaaS. Enterprise pricing is a sales conversation, not a published table.
- **"How much should a coffee cost"** or other non-product pricing -- just answer inline.
- **Project has `business_model` set to `free-self-hosted` or `internal-only`** in the profile -- pricing doesn't apply.

## Prerequisites

- Profile must exist with `business_model` in `{saas-subscription, one-time-purchase, freemium, undecided}`.
- `target_users` on the profile should be specific (vague "everyone" breaks tier design).
- User should have at least 2 competitor price points in hand. The skill will ask if missing -- don't proceed without them.

## Methodology

This skill bakes in the pricing frameworks that apply to solo / small SaaS:

### The Five Decisions

Every pricing model is the product of five decisions. The skill walks them in this order because each downstream decision depends on the ones above:

1. **Value metric** -- what unit scales with customer success? This is the single most consequential choice. Default: per-account (flat). Consider per-seat, per-active-user, per-usage (API calls, clients managed, transactions), or per-outcome (revenue share, deals closed).
2. **Strategy** -- paid-only / free-trial / freemium. Default: **free-trial** for most solo SaaS. Freemium only if you can sustain the free user cost (infrastructure-lean) AND have a clear upgrade moment.
3. **Tier count** -- 3 tiers is the sweet spot (ladder: Starter / Pro / Business). 2 tiers works for very simple products. 4+ creates choice paralysis and rarely earns the extra revenue.
4. **Anchor & ladder** -- the highest tier sets the frame for the rest. Price the top tier at what a *power user* would reasonably pay, not what would feel cheap. Everything below reads as "value" relative to the anchor.
5. **Launch discount** -- beta / early-adopter pricing. Common pattern: launch 30-40% below steady-state, grandfather early users at their price forever, raise prices for new signups after 60-90 days.

### Value metric selection (the #1 mistake)

Default to **per-account** unless customer value genuinely scales with a specific unit. Common misfires:

- Per-seat on tools solo practitioners use alone (like my-project -- trainers work solo; seat-based undermonetizes).
- Per-user on tools where "user" means "customer of the customer" (charge per *managed client*, not per *trainer*).
- Usage metering on tools where usage is chunky/predictable (annoying UX, unpredictable bills).

Decision tree:

```
Does revenue value scale linearly with a specific unit the customer controls?
├-- YES -> that unit IS your value metric (usage, clients managed, transactions)
└-- NO  -> flat per-account pricing is correct
```

### Tier design patterns

For a 3-tier ladder, these shapes work 90% of the time:

- **Ladder by limit** (most common): same feature set, tiers cap usage. Good for metered value. Example: Starter 10 clients / Pro 50 / Business unlimited.
- **Ladder by feature**: tiers unlock features. Good when features cluster by customer maturity. Example: Starter (core) / Pro (+ messaging, progress tracking) / Business (+ team, white-label).
- **Hybrid**: limits + feature gates. Most realistic but hardest to communicate simply.

### Annual discount

Default: **17%** (≈2 months free on a monthly price). This is the near-universal anchor -- customers recognize it. Lower discounts feel cheap; higher discounts signal desperation.

### Psychological pricing

- **$X9 pricing**: $29 reads cheaper than $30 despite the 3% difference. Use it at tier prices.
- **Anchor-high ordering**: list top tier first on pricing page (the "decoy effect"). The script produces PRICING.md in anchor-high order by default.
- **Round annual prices**: $290/year feels cleaner than $348/year. When possible, round the annual to a tidy number (even if the monthly × 10 math is slightly different from the stated discount).

## Operations

### 1. Design (first-time)

**Goal**: Produce version 1 of the pricing model.

**Workflow**:

1. Load the profile:
   ```bash
   python <SUITE_DIR>/scripts/profile_io.py show <slug> --json
   ```
2. Sanity-check preconditions:
   - `business_model` is SaaS-compatible.
   - `target_users` is specific (push back if vague).
3. Ask for **competitor price points** -- minimum 2, ideally 3. Store them in the sidecar.
4. Walk the Five Decisions conversationally. Propose a default for each based on profile + project_type heuristics; let the user override.
5. For tiers, propose names/prices/features based on the ladder pattern chosen. Iterate until the user signs off.
6. Persist:
   ```bash
   echo '<pricing_json>' | python scripts/pricing_tool.py design <slug> --from-stdin
   ```
   The script writes the sidecar, mirrors the active summary to `profile.pricing_model`, renders `PRICING.md`, and updates `last_skill_run`.

### 2. Show

```bash
python scripts/pricing_tool.py show <slug> [--version N] [--json]
```

Default shows the active version. Pass `--version N` to inspect a historical version.

### 3. Iterate

**Goal**: Create a new version based on customer feedback, competitive moves, or conversion data. Archive the previous version with its rationale intact.

**Workflow**:

1. User describes the change and why.
2. Load the current active version, construct the new one.
3. Persist:
   ```bash
   echo '<iteration_json>' | python scripts/pricing_tool.py iterate <slug> --from-stdin
   ```

The iteration payload must include a `reason` field. Like rescope in scope-guardian, this forces documented justification.

Legitimate iteration triggers:
- Conversion rate data (trial -> paid too low, or too high)
- Churn data reveals a tier shape problem
- Customer willingness-to-pay signals (people asking about features that don't exist in higher tiers)
- A real competitor move (not a vibes move)

Not legitimate:
- "I'm second-guessing myself"
- "It's been a week, maybe I should test a new price"
- "I saw a hot take on Twitter"

### 4. Render

```bash
python scripts/pricing_tool.py render <slug> [--output-dir <path>]
```

Re-generates `PRICING.md` from the sidecar. Default output location matches scope-guardian: `<repo>/docs/` if reachable, else staging under the suite's profiles dir.

### 5. Delete

```bash
python scripts/pricing_tool.py delete <slug> [--yes]
```

Removes the sidecar and staged docs. Does NOT touch the profile -- `profile.pricing_model` stays until the user or another skill clears it. (We don't want deleting a pricing session to wipe the agreed-on tier data that Stripe code already references.)

## Output: PRICING.md

Generated doc lives at `<output_dir>/PRICING.md`. Sections:

- **Active Pricing** -- big clean tier table, anchor-high order, monthly + annual, features and limits
- **Billing Model** -- strategy, billing unit, trial period if any, annual discount
- **Competitive Anchors** -- the price points collected during design
- **Launch Pricing** -- if current pricing is pre-launch / early-adopter, a note about when it goes to steady-state
- **Version History** -- links / summaries of prior versions with rationale
- **Stripe Wiring Hints** -- suggested product/price IDs, metadata keys (the developer reference part)

## Sidecar data shape

Authoritative: `templates/pricing.schema.json`. Top-level keys:

- `schema_version` (integer, currently 1)
- `project_slug`
- `created_at` / `updated_at`
- `active_version` -- integer pointer into `versions[]`
- `competitors[]` -- `{name, monthly_price_usd, notes}`
- `versions[]` -- each entry is a full pricing snapshot (see below)
- `change_log[]` -- `{at, change, reason, from_version, to_version}` entries on every iteration

Each entry in `versions[]`:

- `version` -- monotonically increasing integer
- `created_at`, `active_until` -- when this version was current
- `strategy` -- `paid-only | free-trial | freemium`
- `trial_days` -- integer or null
- `billing_unit` -- `per-account | per-seat | per-usage | per-outcome`
- `value_metric` -- free-form description of what scales with value
- `free_tier` -- optional tier object if strategy is `freemium`
- `tiers[]` -- ordered list of paid tiers
- `annual_discount_percent` -- integer
- `launch_strategy` -- `steady-state | early-adopter | beta` with optional grandfather rules
- `rationale` -- why this version exists

Each tier:

- `name` (e.g. "Starter", "Pro", "Business")
- `tagline` -- one-line positioning
- `monthly_price_usd`, `annual_price_usd`
- `features[]` -- bullet list
- `limits` -- object like `{clients: 10, workouts_per_month: null}` where null = unlimited
- `target_segment` -- who this tier is for

## Profile mirror

On every successful write, the skill mirrors a *summary* of the active version to `profile.pricing_model`:

```json
{
  "active_version": 2,
  "strategy": "free-trial",
  "billing_unit": "per-account",
  "trial_days": 14,
  "tier_summary": [
    {"name": "Starter", "monthly_price_usd": 29, "annual_price_usd": 290},
    {"name": "Pro", "monthly_price_usd": 49, "annual_price_usd": 490},
    {"name": "Business", "monthly_price_usd": 99, "annual_price_usd": 990}
  ],
  "annual_discount_percent": 17
}
```

This summary is what other skills (launch-readiness, sprint-planner, integration-mapper) consume. Full history stays in the sidecar.

## Files

```
saas-pricing-architect/
├-- SKILL.md                          # this file
├-- scripts/
│   └-- pricing_tool.py               # design / show / iterate / render / delete
└-- templates/
    ├-- pricing.schema.json           # sidecar JSON Schema
    └-- PRICING.md.tmpl               # rendered doc template
```

## Testing

```bash
# Uses the same test profile pattern as scope-guardian
echo '<profile_json>' | python <SUITE>/scripts/profile_io.py init --from-stdin

echo '{
  "competitors": [{"name":"Trainerize","monthly_price_usd":24,"notes":"market leader"}],
  "version": {
    "strategy": "free-trial",
    "trial_days": 14,
    "billing_unit": "per-account",
    "value_metric": "trainer accounts",
    "tiers": [
      {"name":"Starter","tagline":"Up to 10 clients","monthly_price_usd":29,"annual_price_usd":290,"features":["core"],"limits":{"clients":10},"target_segment":"new"},
      {"name":"Pro","tagline":"Up to 50 clients","monthly_price_usd":49,"annual_price_usd":490,"features":["core","+messaging"],"limits":{"clients":50},"target_segment":"established"}
    ],
    "annual_discount_percent": 17,
    "launch_strategy": "early-adopter",
    "rationale": "Test"
  }
}' | python scripts/pricing_tool.py design <slug> --from-stdin

python scripts/pricing_tool.py show <slug>
python scripts/pricing_tool.py render <slug>
python scripts/pricing_tool.py delete <slug> --yes
```
