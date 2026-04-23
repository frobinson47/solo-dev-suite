# Software Pricing Strategy Skill — Usage Guide

## How to Install

Copy the `software-pricing-strategy/` folder into your Claude Code skills directory:

```bash
# Typical location (adjust to your setup)
cp -r software-pricing-strategy/ ~/.claude/skills/

# Or if you use a project-level CLAUDE.md:
cp -r software-pricing-strategy/ /your/project/.claude/skills/
```

---

## How to Invoke

In any Claude Code session, use any of the following prompts:

```
Analyze the pricing strategy for this repo: https://github.com/user/myapp

Give me a pricing and marketing strategy for the project at ~/projects/my-app

What should I charge for my software at ~/projects/my-app?

Run a full pricing analysis on https://github.com/user/my-project
```

Claude Code will:
1. Read or clone the repo
2. Profile the product and market
3. Build customer personas with WTP estimates
4. Apply pricing framework (demand curve, versioning, bundling, model selection)
5. Generate a full Markdown report and save it to outputs

---

## What the Report Covers

- Product profile (what it is, stack, maturity, license)
- Customer personas (3–5 archetypes with willingness-to-pay estimates)
- Demand curve sketch (revenue at each price point)
- Competitor landscape (price floor, price ceiling)
- Pricing model recommendation (one-time / subscription / freemium / usage / open core)
- Tier/versioning structure (Free / Starter / Team / Enterprise)
- Bundling opportunities
- Launch pricing timeline (Day 1 → Month 3 → Month 6 → Month 12)
- Marketing strategy (messaging, channels, reference point management)
- Risk flags specific to the product
- Prioritized action list

---

## Optional: Add to CLAUDE.md

If you want this skill always available in a specific project, add to your `CLAUDE.md`:

```markdown
## Skills

### Pricing Strategy
When asked to analyze pricing, monetization, marketing strategy, or "what should I
charge", use the skill at `.claude/skills/software-pricing-strategy/SKILL.md`.
The pricing theory reference is at `.claude/skills/software-pricing-strategy/references/pricing-theory.md`.
An example output is at `.claude/skills/software-pricing-strategy/examples/example-output-report.md`.
```

---

## Tips

- **GitHub private repos**: Provide a local path instead, or run `git clone` yourself first
- **Very early-stage projects**: If the repo has no README or clear target user, the skill
  will tell you what the product needs before pricing can be set
- **Already have a price**: Feed the skill your existing price and ask "is this right?" —
  it will validate or suggest adjustments
- **Multiple products**: Run the skill on each separately, then ask Claude to compare
  bundling opportunities across them

---

## Theoretical Basis

This skill is grounded in Neil Davidson's *Don't Just Roll the Dice* (2009), covering:
- Demand curve economics
- Perceived vs. objective value theory
- Reference point psychology
- Versioning and price discrimination
- Bundling math
- Network effects and tipping points
- Switching cost mitigation
- Price as brand signal
- Purchasing threshold awareness
