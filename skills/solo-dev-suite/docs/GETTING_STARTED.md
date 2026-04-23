# Getting Started with Solo Dev Suite

A guided walkthrough for onboarding a new project. Takes about 15-20 minutes for the first project.

## Prerequisites

- Python 3.9+ (stdlib only -- no pip installs)
- All skill folders installed as siblings under the same parent directory
- Claude Code configured to use these skills

## Step 1: Create a project profile

Every skill reads from the central profile. Create one first.

```bash
cd solo-dev-suite

echo '{
  "project_name": "My Project",
  "project_slug": "my-project",
  "description": "One-line description of what this builds",
  "project_type": "saas",
  "primary_stack": ["React", "FastAPI", "PostgreSQL"],
  "hosting": "homelab (Docker)",
  "target_users": "Who uses this and why",
  "business_model": "saas-subscription",
  "available_hours_per_week": 15,
  "current_phase": "scope",
  "repository_path": "D:/path/to/your/repo"
}' | python scripts/profile_io.py init --from-stdin
```

**Fields that matter most:**
- `project_type`: saas, internal-tool, marketing-site, mobile-app, cli-tool, library, plugin
- `business_model`: saas-subscription, free-self-hosted, internal-only, marketplace, undecided
- `current_phase`: scope, architecture, build, ship, grow, sustain
- `repository_path`: where rendered docs (.md files) get written

Verify with `python scripts/profile_io.py show my-project`.

## Step 2: Lock your scope

```bash
cd ../mvp-scope-guardian
echo '{
  "features": [
    {"name": "User auth", "bucket": "launch-blocking", "effort": "M", "impact": "high", "rationale": "No app without login"},
    {"name": "Admin dashboard", "bucket": "post-launch-v1.1", "effort": "L", "impact": "medium", "rationale": "Can manage via DB initially"},
    {"name": "Dark mode", "bucket": "parking-lot", "effort": "S", "impact": "low", "rationale": "Nice to have, not blocking"}
  ]
}' | python scripts/scope_tool.py lock my-project --from-stdin
```

This creates the scope sidecar and renders `MVP_SCOPE.md` in your repo.

## Step 3: Design pricing (if SaaS)

```bash
cd ../saas-pricing-architect
echo '{
  "competitors": [
    {"name": "Competitor A", "monthly_price_usd": 29},
    {"name": "Competitor B", "monthly_price_usd": 49}
  ],
  "version": {
    "strategy": "freemium",
    "billing_unit": "per-account",
    "value_metric": "number of active users",
    "free_tier": {
      "name": "Free",
      "features": ["Basic features"],
      "limits": {"users": 3},
      "upgrade_trigger": "4th user added"
    },
    "tiers": [
      {
        "name": "Pro",
        "monthly_price_usd": 29,
        "annual_price_usd": 278,
        "features": ["Everything in Free", "Premium features"],
        "limits": {"users": 50},
        "target_segment": "Small teams"
      }
    ],
    "annual_discount_percent": 20,
    "launch_strategy": {"mode": "beta"},
    "rationale": "Why this pricing makes sense"
  }
}' | python scripts/pricing_tool.py design my-project --from-stdin
```

This populates `profile.pricing_model`, which launch-readiness and auto-docs will read later.

## Step 4: Map integrations

```bash
cd ../integration-mapper
echo '{
  "reason": "Why this service is needed",
  "service": {
    "name": "Stripe",
    "purpose": "Payment processing",
    "category": "payments",
    "blast_radius": {"rating": "critical", "rationale": "All revenue flows through it"},
    "pricing_exposure": {"rating": "high", "current_cost_usd_per_month": 0, "notes": "2.9% + 30c per txn"},
    "deprecation_risk": {"rating": "low", "notes": "Market leader"},
    "fallback": {"plan": "Manual invoicing", "tested": false, "notes": "Emergency only"},
    "review_cadence": "quarterly"
  }
}' | python scripts/integration_tool.py add my-project --from-stdin
```

Repeat for each third-party service. This populates `profile.third_party_services`.

## Step 5: Update phase and continue

As your project progresses, update the phase:

```bash
cd ../solo-dev-suite
echo '{"current_phase": "build"}' | python scripts/profile_io.py update my-project --from-stdin
```

Then check what skills are relevant:

```bash
python scripts/list_skills.py --slug my-project
```

## Recommended skill order by phase

| Phase | Skills to run |
|-------|--------------|
| **scope** | mvp-scope-guardian, saas-pricing-architect |
| **architecture** | integration-mapper, adr-generator |
| **build** | tech-debt-register, testing-strategy, adr-generator |
| **ship** | launch-readiness, security-audit, auto-docs |
| **sustain** | auto-docs, tech-debt-register |

## Tips

- **All skills are re-runnable.** Run scope guardian again after you add features. Run security audit again after you add a new integration.
- **Profile mirrors flow automatically.** When you design pricing, the pricing summary flows to `profile.pricing_model`. When launch-readiness runs next, it reads that and tailors its checklist.
- **Rendered docs go to your repo.** If `repository_path` is set, skills write `.md` files to `<repo>/docs/`. These are the human-readable output you commit alongside your code.
- **Use `show` before `render`.** Every skill has a `show` command that displays the current state in the terminal. `render` writes the markdown file.
- **Delete is non-destructive to .md files.** Deleting a sidecar removes the JSON data but leaves rendered markdown in your repo (it's version-controlled there).
