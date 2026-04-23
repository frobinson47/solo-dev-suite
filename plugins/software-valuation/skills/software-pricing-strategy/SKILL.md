---
name: software-pricing-strategy
description: |
  Analyzes a software product from a local folder path OR a GitHub URL and produces a
  comprehensive, structured pricing and marketing strategy report. Use this skill any time
  a user wants to price their software, evaluate monetization options, build a go-to-market
  strategy, or understand what their product is worth to different customer segments.

  Trigger phrases include: "price my software", "pricing strategy for my project", "how
  should I charge for this", "what should I sell this for", "marketing strategy for my app",
  "monetization plan", "help me price [product name]", or any time the user provides a
  GitHub URL or local folder and asks about pricing, selling, or monetizing.

  This skill is also appropriate when the user just shares a repo and asks "what do you
  think?" — always consider whether pricing guidance would be valuable in that context.
---

# Software Pricing Strategy Skill

A four-phase framework for analyzing any software product and delivering a concrete,
evidence-based pricing and marketing strategy. Works with local directories or GitHub URLs.

---

## Phase 0 — Input Normalization

Before doing anything else, determine the input type:

### Local Path
If the user provides a local folder (e.g. `~/projects/myapp` or `/home/user/my-app`):
```bash
ls -la <path>
```
Proceed directly to Phase 1 from that directory.

### GitHub URL
If the user provides a GitHub URL (e.g. `https://github.com/user/repo`):
```bash
# Extract owner/repo from URL
# Clone to a temp working directory
git clone --depth=1 <url> /tmp/pricing-analysis-target
cd /tmp/pricing-analysis-target
```
If the clone fails (private repo, bad URL), inform the user and ask for a local path or
a zip export instead.

### Fallback
If neither is provided, ask: *"Please provide either a local folder path or a GitHub URL
for the software you'd like to analyze."*

---

## Phase 1 — Product Discovery

Read the repository systematically. The goal is to understand **what the software is**,
**who it is for**, and **what problem it solves**. Do not guess — read the actual files.

### 1A. Mandatory Files (read every one that exists)

Run this inventory first:
```bash
find . -maxdepth 3 \( \
  -name "README*" -o -name "readme*" \
  -o -name "DESCRIPTION*" \
  -o -name "package.json" \
  -o -name "pyproject.toml" -o -name "setup.py" -o -name "setup.cfg" \
  -o -name "Cargo.toml" \
  -o -name "go.mod" \
  -o -name "Gemfile" \
  -o -name "composer.json" \
  -o -name "*.csproj" \
  -o -name "pom.xml" \
  -o -name "build.gradle" \
  -o -name "CHANGELOG*" -o -name "changelog*" \
  -o -name "LICENSE*" \
  -o -name "PRICING*" -o -name "pricing*" \
  -o -name "MONETIZATION*" \
  -o -name "docs" -type d \
  -o -name "landing*" -o -name "marketing*" \
\) 2>/dev/null | head -60
```

Then read each found file. Pay special attention to:
- **README**: Product description, features, target audience, screenshots, demo links
- **package.json / pyproject.toml / Cargo.toml**: Name, description, keywords, dependencies
- **CHANGELOG**: Release history — is this v0.1 or v5? How actively developed?
- **LICENSE**: Open source or proprietary? This matters enormously for pricing.
- Any existing pricing page or monetization notes

### 1B. Feature Surface Area

Get a high-level sense of what the software actually does:
```bash
# Count lines of code by language
find . -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" \
  -o -name "*.rs" -o -name "*.go" -o -name "*.rb" -o -name "*.cs" \
  2>/dev/null | xargs wc -l 2>/dev/null | tail -1

# Top-level directory structure
ls -d */ 2>/dev/null || ls

# Dependency count (signals product complexity and maturity)
cat package.json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
deps=len(d.get('dependencies',{}))
dev=len(d.get('devDependencies',{}))
print(f'Runtime deps: {deps}, Dev deps: {dev}')
" 2>/dev/null || true
```

### 1C. Discovery Extraction Checklist

After reading the files, synthesize the following. **Do not proceed to Phase 2 until you
can answer all of these** (even if the answer is "unclear / not documented"):

| Field | Answer |
|---|---|
| Product Name | |
| One-sentence description | |
| Primary language / stack | |
| Product category | (CLI tool / desktop app / web app / SaaS / API / library / SDK / game / mobile app) |
| Deployment model | (self-hosted / cloud SaaS / local / hybrid) |
| Open source? | (MIT / GPL / proprietary / source-available) |
| Maturity stage | (prototype / alpha / beta / v1+ / mature) |
| Target user (primary) | |
| Target user (secondary) | |
| Core problem solved | |
| Top 3 features | |
| Integration ecosystem | (standalone / plugs into X, Y, Z) |
| Existing monetization? | (none / freemium / paid / OSS with pro tier) |
| Docs quality | (none / minimal README / full docs site) |
| Known competitors | (from README, docs, or pkg keywords) |

### 1D. Brand Name Clearance Audit

Before pricing a product, verify the product name is defensible and not crowded.
A name collision creates real business risk — trademark disputes, App Store
rejection, customer confusion, or (as in real cases) a buyer perceiving conflict
of interest with an employee's surname.

#### Automated Searches

Run all of the following searches using web search. For each, record what you find:

**1. Domain Availability**
Search for the product name across key TLDs:
- .com, .io, .app, .dev, .co, .net, .org, .software
- Note which are taken, parked, or active competitors

**2. App Store Presence**
- Apple App Store: search "[product name]" — note exact matches AND close variants
- Google Play Store: search "[product name]" — same
- Record: app name, publisher, category, approximate install count

**3. Trademark Registry Search**
- USPTO TESS: search for the product name and phonetic equivalents
- EU EUIPO: if international sales are planned
- Record: mark text, registration status (live/dead), goods/services class,
  owner, filing date

**4. Copyright Registry**
- US Copyright Office: search for the product name in title records
- Note any registered works with identical or confusingly similar names

**5. General Web Presence**
- Search: "[product name] software", "[product name] app", "[product name] tool"
- Search: "[product name] [industry keyword]" (e.g., "[product name] fleet")
- Record: competing products, open source projects, companies using the name

**6. Phonetic / Visual Similarity Scan**
- Identify names that SOUND like the product name (sound-alikes)
- Identify names that LOOK like the product name (look-alikes, typo-squats)
- Check if any sound-alikes or look-alikes are trademarked or established

#### Clearance Report Table

| Check | Findings | Risk Level |
|---|---|---|
| .com domain | Available / Taken by [X] | LOW / MEDIUM / HIGH |
| Other TLDs | [summary] | LOW / MEDIUM / HIGH |
| Apple App Store | [N] results, [M] exact/close matches | LOW / MEDIUM / HIGH |
| Google Play Store | [N] results, [M] exact/close matches | LOW / MEDIUM / HIGH |
| USPTO trademarks | [N] live marks in relevant classes | LOW / MEDIUM / HIGH |
| EUIPO trademarks | [N] live marks | LOW / MEDIUM / HIGH |
| Copyright records | [findings] | LOW / MEDIUM / HIGH |
| Web presence | [N] competing products | LOW / MEDIUM / HIGH |
| Sound-alikes | [list] | LOW / MEDIUM / HIGH |
| Look-alikes | [list] | LOW / MEDIUM / HIGH |

#### Overall Name Risk Assessment

Rate the name with one of three levels:

**GREEN** — Name is clear across all registries, minimal competition, safe to invest in branding
**YELLOW** — Some conflicts exist but in different industries/classes; proceed with caution
**RED** — Crowded namespace, active trademarks in same class, or high confusion risk

#### If YELLOW or RED: Name Alternatives

When the namespace is crowded, generate 5–10 alternative name suggestions that:
- Preserve the core concept/metaphor of the original name
- Are clear across the same checks (spot-check top 3 candidates)
- Work as domain names (check .com and primary TLD availability)
- Are distinct from existing trademarks in the relevant goods/services class

**IMPORTANT**: Flag name risk prominently in the Executive Summary if YELLOW or RED.
A great pricing strategy is worthless if the product faces a C&D letter on launch day.

---

## Phase 2 — Customer & Market Profiling

This phase translates Discovery data into a structured view of the market. Follow each
section in order.

### 2A. Customer Segmentation

Identify **3–5 realistic buyer personas** for this product. For each persona, estimate:

- **Name / archetype** (e.g. "Solo developer", "Startup CTO", "Enterprise DevOps team")
- **Job to be done**: What task does this product complete for them?
- **Time saved or pain removed**: Quantify if possible (hours/week, errors avoided, etc.)
- **Budget authority**: Personal card? Team budget? IT procurement?
- **Price sensitivity**: High / Medium / Low — and why
- **Estimated willingness to pay (WTP)**: Single number or range in USD/month or USD/one-time

Apply the Davidson framework: *"A rational buyer should pay up to the dollar value of the
benefit they receive."* But humans are not rational — perceived value matters more than
objective value. For each persona, note whether perceived value is likely **higher** or
**lower** than objective value, and why.

### 2B. Demand Curve Sketch

Using the personas from 2A, sketch a rough demand curve table:

| Price Point | Likely Buyers | Estimated Revenue |
|---|---|---|
| Free | All personas | $0 |
| $X (low) | Most personas | $X × N |
| $Y (mid) | Some personas | $Y × M |
| $Z (high) | Premium/enterprise only | $Z × P |
| $W (too high) | Nobody | $0 |

Identify the **revenue-maximizing price band** — this is the row with the largest estimated
revenue, and becomes the baseline for your recommendation.

### 2C. Reference Point Analysis

Answer these questions:
1. What will buyers **Google first** when looking for this product? What will they find?
2. What is the **market standard price** for tools in this category?
3. Is there a dominant free/open-source alternative that anchors expectations at $0?
4. Are there premium players whose high prices make your potential price look reasonable?

Use these reference points to determine whether the product needs to **differentiate
upward** (justify a premium), **match the market** (compete on features), or **own the
low end** (race to win on accessibility/price).

### 2D. Switching Cost Assessment

For each primary persona:
- What do they use today to solve this problem?
- What is the **economic switching cost** (time to migrate, learn, integrate)?
- What is the **psychological switching cost** (attachment to current tool, fear of change)?

If switching costs are high: pricing must overcome them — free trials, migration tools,
money-back guarantees, or import compatibility are critical.

If switching costs are low: price wars are a real risk. Differentiation via brand,
community, or unique features becomes essential.

### 2E. Competitive Landscape

Search the web for direct competitors if internet is available:
```bash
# If web_search tool is available, search for:
# "[product category] pricing [year]"
# "[product name] alternatives"
# "[primary keyword from README] software pricing"
```

Build a competitor table:

| Competitor | Price Model | Entry Price | Top Tier | Notes |
|---|---|---|---|---|
| Competitor A | Freemium | Free | $X/mo | |
| Competitor B | One-time | $Y | $Z (pro) | |
| Competitor C | Per-seat | $A/seat | Enterprise | |

Identify the **price floor** (cheapest credible competitor) and **price ceiling** (most
expensive established player) for this category.

---

## Phase 3 — Pricing Framework Application

Apply each framework from the Davidson model. Score each one as **Recommended / Consider /
Skip** for this specific product.

### 3A. Base Pricing Model Selection

Evaluate these models for fit:

**One-time perpetual license**
- Best for: Developer tools, desktop apps, self-hosted utilities
- Pros: Simple, no churn, high perceived value
- Cons: Revenue cliffs between versions, no recurring income
- Fit score: [HIGH / MEDIUM / LOW] — explain why

**Subscription (monthly/annual)**
- Best for: SaaS, cloud-hosted, frequently updated products
- Pros: Predictable revenue, aligns cost with ongoing value delivery
- Cons: Churn risk, must deliver continuous value to justify
- Fit score: [HIGH / MEDIUM / LOW] — explain why

**Freemium (free base + paid upgrade)**
- Best for: Products with strong network effects, developer tools, high-volume consumer apps
- Warning: Free tier must be good enough to be useful but not so good it kills conversion.
  Flickr converts ~5% of free users. Plan accordingly.
- Fit score: [HIGH / MEDIUM / LOW] — explain why

**Usage-based / metered pricing**
- Best for: APIs, compute-heavy tools, storage products, anything with clear consumption units
- Pros: Scales with customer value
- Cons: Unpredictable bills cause customer anxiety; hard to forecast revenue
- Fit score: [HIGH / MEDIUM / LOW] — explain why

**Gillette / razor-blade model**
- Best for: Products with a free/cheap core that generates ongoing paid consumption
  (e.g. free CLI tool + paid cloud sync, free generator + paid credits)
- Fit score: [HIGH / MEDIUM / LOW] — explain why

**Open core (OSS + commercial)**
- Best for: Developer infrastructure, databases, CLI tools with enterprise needs
- Model: Community edition free and open; enterprise edition adds SSO, audit logs, SLA, support
- Fit score: [HIGH / MEDIUM / LOW] — explain why

**Consulting / services wrapper**
- Best for: Complex enterprise tools where buyers need implementation help
- Fit score: [HIGH / MEDIUM / LOW] — explain why

**RECOMMENDATION**: State the single best model (or hybrid) with a one-paragraph rationale.

### 3B. Versioning Strategy

Can this product be offered in multiple tiers? For each potential tier, specify:

| Tier Name | Target Persona | Key Differentiators | Suggested Price |
|---|---|---|---|
| Free / Community | (who gets this?) | (what's included / excluded?) | $0 |
| Starter / Indie | (who?) | (what features unlock?) | $X |
| Pro / Team | (who?) | (what features?) | $Y |
| Enterprise / Business | (who?) | (SSO, SLA, audit, custom) | $Z or "Contact us" |

**Versioning warnings to flag if applicable:**
- If tier differences are hard to compare (like the Vista OS debacle), warn that buyers will
  flee to extremes (cheapest or most expensive) or defer the purchase entirely.
- If the free tier is too generous, flag cannibalization risk.
- Keep feature differences simple and clearly communicable.

### 3C. Bundling Opportunities

Identify any **natural bundles**:
- Does the repo contain multiple tools or modules that could be sold separately but bundled?
- Are there natural companion products (templates, presets, integrations) that could be added?
- Could you bundle with related third-party tools for a "pro kit" offering?

For each bundle candidate, apply the bundling revenue math:
- What does Persona A value most?
- What does Persona B value most?
- Would a bundle priced at (A's WTP + B's WTP) / some discount be accepted by both?

### 3D. Network Effects Check

Does this product have network effects? (i.e., does its value increase as more people use it?)

Examples: collaboration features, shared templates, community marketplaces, public leaderboards,
integrations that require other users to also use the tool.

**If YES**: Free pricing at launch is strongly recommended to hit the adoption tipping point.
Monetize post-tipping-point via premium features or enterprise tier.

**If NO**: Standard demand-curve pricing applies. Don't give away value unnecessarily.

### 3E. Piracy / Cracking Risk Assessment

For desktop/offline software:
- Is this the type of product where pirates could redistribute it easily?
- If yes: consider whether high pricing is sustainable, or whether it just encourages
  piracy while free/legitimately acquired copies do the brand building.
- Adobe Photoshop strategy: keep price high ($700), let pirates "aspire to own it legally."
  This works when brand cachet is high. For most indie software, it doesn't work.
- Better approach for most: price at a point where paying is easier than pirating.

### 3F. Purchasing Threshold Analysis

Identify which **organizational spending thresholds** the pricing should target or avoid:

| Threshold | Typical Rule | Implication |
|---|---|---|
| < $10 | Personal card, no approval | Impulse buy — maximize volume |
| $10–$50 | Personal card, may expense | Low friction — still impulse adjacent |
| $50–$999 | Boss's card, verbal OK | Needs clear ROI justification |
| $1,000–$4,999 | Formal approval required | Needs champion inside org |
| $5,000–$24,999 | Department head approval | Enterprise sales motion required |
| $25,000+ | CEO / board visibility | Long sales cycle, legal review |

**Recommendation**: State whether the product should price **just under** a threshold
or whether crossing a threshold is justified by the product's enterprise readiness.

### 3G. Price Signaling Analysis

What does the proposed price communicate about the product?

- High price (relative to market): signals quality, seriousness, enterprise-readiness
- Low price: signals accessibility — but risks "toy" perception if market norm is higher
- Free: signals low commitment on seller's part OR strong network-effect land-grab strategy
- Matching competitors exactly: signals "me too" — dangerous without differentiation

Assess whether the recommended price sends the **right signal** for this product's brand
positioning and target buyer.

---

## Phase 4 — Report Generation

Generate a complete **Software Pricing & Marketing Strategy Report** as a structured
Markdown document. Save it as `pricing-strategy-report.md` in `/home/claude/` then copy
to `/mnt/user-data/outputs/`.

### Report Structure

```
# Pricing & Marketing Strategy Report
## [Product Name]
Generated: [date]

---

## Executive Summary
[3–5 sentence overview of the product, the market opportunity, and the top recommendation]

---

## Product Profile
[Completed Discovery table from Phase 1C]

---

## Brand Name Clearance
[Clearance report table from Phase 1D]
[Overall risk assessment: GREEN / YELLOW / RED]
[Alternative name suggestions if applicable]

---

## Customer Segments
[3–5 personas with WTP estimates and value analysis]

---

## Market Landscape
[Competitor table + reference point analysis]
[Price floor and ceiling]

---

## Demand Curve Analysis
[Demand curve table with estimated revenue at each price point]
[Revenue-maximizing price band identified]

---

## Pricing Model Recommendation
### Primary Model: [Name]
[Rationale paragraph]

### Tier Structure
[Versioning table]

### Bundling Opportunities
[Bundle analysis]

---

## Switching Costs & Positioning
[How to overcome switching costs]
[Key differentiators to promote]

---

## Launch Pricing Strategy
[What to charge on day 1]
[What to change at 6 months]
[What to change at 12 months]
[How to handle early adopter pricing]

---

## Marketing Strategy
### Perceived Value Enhancement
[Specific tactics for this product — personality, tribe, demos, content, etc.]

### Reference Point Management
[Which comparisons to encourage, which to avoid]

### Channel Strategy
[How to sell: web-only, marketplace, direct, resellers, OSS community]

### Key Messaging Pillars
[3 messages that justify the price and differentiate from alternatives]

---

## Risk Flags
[Specific pricing pitfalls to watch for this product]
[e.g., price war risk, cannibalization risk, enterprise threshold issues]

---

## Pricing Checklist
[Completed version of the Davidson checklist tailored to this product]

---

## Recommended Next Steps
[Ordered action list: what to do first, second, third]
```

---

## Output Delivery

After generating the report:

1. Save to `/mnt/user-data/outputs/pricing-strategy-report.md`
2. Present the file to the user using `present_files`
3. Provide a verbal summary of the **top 3 most important findings** — keep it to 3–5
   sentences, not a wall of text
4. Offer to go deeper on any specific section (versioning math, competitive positioning,
   launch pricing, etc.)

---

## Quality Rules

- **Never fabricate competitor prices** — if web search isn't available, say so and instruct
  the user to fill in the competitor table manually.
- **Anchor every recommendation** to a specific observation from the repo. "We recommend
  subscription pricing because the README shows active weekly releases and a hosted cloud
  component" — not generic advice.
- **Flag when the product is too early to price** — if the repo is clearly a personal
  experiment with no README, no target user, and no features, say so directly:
  *"This product isn't ready to price yet. Here's what it needs first: [list]."*
- **Don't conflate OSS and monetization** — if the product is MIT-licensed, open-source
  monetization strategies (open core, SaaS wrapper, consulting) must be addressed separately
  from any commercial licensing plan.
- **Apply the "practice trumps theory" principle** — always end with a concrete first price
  to try, not just a framework. Indecision is worse than a suboptimal price.

---

## Reference Frameworks Embedded In This Skill

This skill applies the following frameworks, drawn from Neil Davidson's
*Don't Just Roll the Dice* and standard SaaS/software monetization research:

1. **Demand curve analysis** — price × volume = revenue; find the revenue-maximizing rectangle
2. **Perceived vs. objective value** — customers pay for what they *think* something is worth
3. **Reference point theory** — anchor comparisons to favorable benchmarks, not unfavorable ones
4. **Versioning / price discrimination** — extract maximum value by serving multiple WTP levels
5. **Bundling math** — heterogeneous preferences can unlock revenue invisible in individual pricing
6. **Network effects tipping point** — free pricing to drive adoption past the critical mass threshold
7. **Switching cost mitigation** — economic and psychological barriers must be addressed in pricing
8. **Purchasing threshold awareness** — price just under organizational approval thresholds
9. **Price as signal** — the number you charge communicates brand quality and intent
10. **Value-based pricing** — price to the benefit delivered, not to the cost incurred
