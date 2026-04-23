---
name: market-feasibility-report
description: |
  Takes a software product idea — described in plain text, a pitch document, a notes file,
  or a conversational description — and produces a comprehensive Market Feasibility Report.
  The report assesses the idea's viability across seven dimensions: technical, economic,
  legal/regulatory, operational, scheduling, market/commercial, and pricing strategy.

  This skill does NOT require a codebase. It works from an idea description alone, though
  it can optionally incorporate an existing repo, prototype, or design document if provided.

  Trigger phrases include: "feasibility study", "is this idea viable", "should I build this",
  "market feasibility", "can this work", "evaluate this idea", "assess this project",
  "business viability", "feasibility report", "will this sell", "is there a market for",
  or any time the user describes a software product concept and asks whether it's worth pursuing.

  This skill is also appropriate when the user pitches an idea and asks "what do you think?" —
  always consider whether a feasibility assessment would be valuable in that context.
---

# Market Feasibility Report Skill

A comprehensive framework for evaluating the viability of a software product idea across
technical, economic, legal, operational, scheduling, and market dimensions — culminating
in a full pricing strategy and go-to-market plan. Works from idea descriptions, pitch
documents, or conversational input.

---

## Phase 0 — Input Capture & Idea Clarification

Unlike codebase analysis, this skill starts from an **idea** — which may be vague, partial,
or spread across multiple inputs. The first job is to crystallize the idea into something
concrete enough to evaluate.

### 0A. Accepted Input Types

The user may provide any of the following:
- **Plain text description** in the conversation ("I want to build an app that...")
- **A document or file** (pitch deck, business plan, PRD, notes file, markdown doc)
- **A GitHub URL or local path** to an early prototype or proof-of-concept
- **A combination** of the above

If a file path or URL is provided, read it:
```bash
# For a local file or directory
ls -la <path>
cat <path>  # if it's a document

# For a GitHub URL (early prototype)
git clone --depth=1 <url> /tmp/feasibility-analysis-target
```

### 0B. Idea Extraction Checklist

After consuming all inputs, extract the following. If the user hasn't provided enough
detail, **ask clarifying questions** — but batch them into a single round. Do not ask
more than 5-7 questions at once. Mark unknown fields as "TBD — needs user input" and
proceed with reasonable assumptions where possible.

| Field | Answer |
|---|---|
| Working product name | |
| One-sentence elevator pitch | |
| Problem being solved | |
| Who has this problem? (target users) | |
| Proposed solution approach | |
| Product category | (CLI / desktop app / web app / SaaS / API / library / mobile app / marketplace / hardware+software) |
| Deployment model | (self-hosted / cloud / local / hybrid / app store) |
| Revenue intent | (venture-backed / bootstrapped / side project / open source / internal tool) |
| Existing assets | (nothing yet / wireframes / prototype / MVP / partial codebase) |
| Solo founder or team? | |
| Target launch timeframe | |
| Budget range | (bootstrapping / <$10K / $10K-$50K / $50K-$250K / $250K+) |

### 0C. Assumption Declaration

Before proceeding, explicitly state **every assumption** you are making about the idea.
The user must be able to see and correct these before the analysis proceeds. Format:

> **Assumptions made for this analysis:**
> 1. [assumption] — *assumed because [reason]*
> 2. [assumption] — *assumed because [reason]*
> ...
>
> *If any of these are wrong, let me know and I'll adjust the analysis.*

---

## Phase 1 — Market & Commercial Feasibility

This phase determines whether there is a real market for the idea and whether the product
can capture meaningful demand.

### 1A. Problem Validation

Answer these critical questions using web research:

1. **Is this a real problem?** Search for people complaining about this problem online
   (forums, Reddit, Twitter/X, Hacker News, Stack Overflow, Quora). Quantify signal:
   - How many people are discussing this pain point?
   - How recently? (Active problem vs. solved problem)
   - How intensely? (Minor annoyance vs. hair-on-fire problem)

2. **How are people solving this today?** (existing solutions, workarounds, manual processes)

3. **Why haven't existing solutions fully solved it?** (too expensive, too complex,
   wrong audience, missing features, bad UX)

4. **Is the problem growing or shrinking?** Look for trends:
   - Industry growth data
   - Regulatory changes creating new needs
   - Technology shifts enabling new solutions
   - Demographic or behavioral trends

### 1B. Market Sizing (TAM / SAM / SOM)

Estimate the addressable market using a **bottom-up** approach (preferred) with a
**top-down** sanity check:

**Bottom-Up (primary)**:
```
Number of potential users/companies with this problem × Average revenue per user = SAM
SAM × Realistic capture rate (1-5% for startups) = SOM
```

**Top-Down (sanity check)**:
```
Total market spending in the category × % addressable by this product type = TAM
TAM × % reachable by a new entrant = SAM
```

Present as a table:

| Metric | Estimate | Methodology |
|---|---|---|
| TAM (Total Addressable Market) | $X | [how calculated] |
| SAM (Serviceable Addressable Market) | $Y | [how calculated] |
| SOM (Serviceable Obtainable Market) | $Z | [how calculated] |

Flag if the SOM is below $100K/year — this may be a viable side project but not a
sustainable business unless costs are near zero.

### 1C. Competitive Landscape

Search the web for direct and indirect competitors:
```
# Search queries to run:
# "[problem description] software"
# "[product category] tools [year]"
# "[product name] alternatives" (if a known competitor exists)
# "[target user] [problem] solution"
```

Build a competitor matrix:

| Competitor | Type | Price | Strengths | Weaknesses | Market Position |
|---|---|---|---|---|---|
| [name] | Direct / Indirect | $X | | | Leader / Challenger / Niche |

Assess:
- **Market saturation**: Is this a blue ocean (few competitors) or red ocean (crowded)?
- **Incumbent strength**: Are competitors well-funded, well-established, or vulnerable?
- **Differentiation potential**: What unique angle could this product own?
- **Timing**: Is the market early (land-grab opportunity) or mature (displacement required)?

### 1D. Customer Segmentation & Personas

Identify **3-5 realistic buyer personas**. For each:

- **Name / archetype** (e.g., "Solo Developer", "Startup CTO", "Enterprise DevOps Lead")
- **Job to be done**: What task does this product complete for them?
- **Current solution**: What do they use today?
- **Pain intensity**: 1-10 scale — how badly do they need this solved?
- **Budget authority**: Personal card? Team budget? IT procurement?
- **Price sensitivity**: High / Medium / Low — and why
- **Estimated willingness to pay (WTP)**: USD/month or USD/one-time range
- **Perceived vs. objective value**: Is perceived value likely higher or lower than
  objective value, and why?

### 1E. Brand Name Clearance Audit

Before investing in a name, verify it's defensible and not crowded.

#### Automated Searches

Run all of the following using web search. For each, record findings:

**1. Domain Availability**
Search across key TLDs:
- .com, .io, .app, .dev, .co, .net, .org, .software
- Note which are taken, parked, or active competitors

**2. App Store Presence**
- Apple App Store: search "[product name]" — note exact matches AND close variants
- Google Play Store: search "[product name]" — same
- Record: app name, publisher, category, approximate install count

**3. Trademark Registry Search**
- USPTO TESS: search for the product name and phonetic equivalents
- EU EUIPO: if international sales are planned
- Record: mark text, registration status (live/dead), goods/services class, owner, filing date

**4. Copyright Registry**
- US Copyright Office: search for the product name in title records
- Note any registered works with identical or confusingly similar names

**5. General Web Presence**
- Search: "[product name] software", "[product name] app", "[product name] tool"
- Search: "[product name] [industry keyword]"
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

Rate with one of three levels:

**GREEN** — Name is clear across all registries, minimal competition, safe to invest in branding
**YELLOW** — Some conflicts exist but in different industries/classes; proceed with caution
**RED** — Crowded namespace, active trademarks in same class, or high confusion risk

#### If YELLOW or RED: Name Alternatives

Generate 5-10 alternative name suggestions that:
- Preserve the core concept/metaphor of the original name
- Are clear across the same checks (spot-check top 3 candidates)
- Work as domain names (check .com and primary TLD availability)
- Are distinct from existing trademarks in the relevant goods/services class

**IMPORTANT**: Flag name risk prominently in the Executive Summary if YELLOW or RED.

---

## Phase 2 — Technical Feasibility

This phase determines whether the product can actually be built with available
technology, skills, and resources.

### 2A. Technical Requirements Analysis

Based on the idea description, identify:

| Requirement | Details | Complexity |
|---|---|---|
| Core functionality | [what must the product do at minimum?] | LOW / MEDIUM / HIGH |
| Data storage needs | [type, volume, sensitivity] | LOW / MEDIUM / HIGH |
| Integration requirements | [APIs, third-party services, protocols] | LOW / MEDIUM / HIGH |
| Performance requirements | [latency, throughput, concurrency] | LOW / MEDIUM / HIGH |
| Security requirements | [auth, encryption, compliance] | LOW / MEDIUM / HIGH |
| Infrastructure needs | [hosting, CDN, scaling] | LOW / MEDIUM / HIGH |
| Platform targets | [web, mobile, desktop, CLI, API] | LOW / MEDIUM / HIGH |

### 2B. Recommended Technology Stack

Propose a technology stack with rationale:

| Layer | Recommendation | Why | Alternatives |
|---|---|---|---|
| Frontend | | | |
| Backend | | | |
| Database | | | |
| Infrastructure | | | |
| Auth | | | |
| Payments | | | |
| Monitoring | | | |
| CI/CD | | | |

Consider:
- **Founder/team skillset**: If the user mentioned their background, recommend stack
  that aligns with existing skills
- **Hiring market**: Is talent available for this stack?
- **Ecosystem maturity**: Are the tools battle-tested or bleeding-edge?
- **Cost at scale**: How does infrastructure cost grow with users?

### 2C. Technical Risk Assessment

Identify specific technical risks:

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| [e.g., "Real-time sync is complex"] | HIGH/MED/LOW | HIGH/MED/LOW | [approach] |
| [e.g., "ML model accuracy unknown"] | | | |
| [e.g., "Third-party API dependency"] | | | |

Flag any **technical blockers** — things that could make the project impossible:
- Required technology that doesn't exist yet
- Performance requirements that exceed current state-of-the-art
- Data requirements that can't be legally obtained
- Integration dependencies on services with no public API

### 2D. Build vs. Buy Analysis

For each major component, evaluate whether to build custom or use existing services:

| Component | Build | Buy/Use | Recommendation | Rationale |
|---|---|---|---|---|
| Auth system | Custom | Auth0/Clerk/Supabase Auth | | |
| Payments | Custom | Stripe/Paddle | | |
| Email | Custom | SendGrid/Resend | | |
| [etc.] | | | | |

### 2E. MVP Definition

Define the **minimum viable product** — the smallest version that tests the core
value proposition:

- **Must-have features** (launch blockers)
- **Should-have features** (week 2-4 additions)
- **Nice-to-have features** (future roadmap)
- **Explicitly out of scope** for MVP

Estimate MVP scope in terms of:
- Number of screens/endpoints/components
- Approximate lines of code (order of magnitude)
- Key technical unknowns that MVP must resolve

---

## Phase 3 — Financial & Economic Feasibility

This phase models the economics — can this product make money, and how much
investment does it require?

### 3A. Development Cost Estimation

Estimate costs to reach MVP and then v1:

**MVP (Minimum Viable Product)**:

| Cost Category | Low Estimate | High Estimate | Assumptions |
|---|---|---|---|
| Development (labor) | | | [hours × rate] |
| Design (UI/UX) | | | |
| Infrastructure (first 6 months) | | | |
| Third-party services/APIs | | | |
| Legal (incorporation, terms, privacy) | | | |
| Domain & branding | | | |
| **Total MVP Cost** | | | |

**v1.0 (Market-ready product)**:

| Cost Category | Low Estimate | High Estimate | Assumptions |
|---|---|---|---|
| Additional development | | | |
| QA & testing | | | |
| Documentation | | | |
| Marketing launch | | | |
| **Total v1.0 Cost** | | | |

Adjust estimates based on the user's situation:
- Solo founder coding it themselves? Labor cost = opportunity cost, not salary
- Hiring contractors? Use market rates ($50-$200/hr depending on region and skill)
- Using AI-assisted development? Factor in productivity multiplier (1.5-3x)

### 3B. Operating Cost Projection (Monthly Burn)

| Cost | Month 1-3 | Month 4-6 | Month 7-12 | Year 2 |
|---|---|---|---|---|
| Hosting/infra | | | | |
| Third-party APIs | | | | |
| Support tools | | | | |
| Marketing/ads | | | | |
| Team (if any) | | | | |
| Legal/accounting | | | | |
| **Monthly Total** | | | | |

### 3C. Revenue Projection

Using the demand curve from Phase 1 personas and WTP estimates:

| Scenario | Month 3 | Month 6 | Month 12 | Year 2 |
|---|---|---|---|---|
| Conservative | | | | |
| Moderate | | | | |
| Optimistic | | | | |

State assumptions clearly for each scenario (conversion rates, growth rates,
churn rates, ARPU).

### 3D. Break-Even Analysis

```
Break-even point = Total Fixed Costs / (Revenue per Customer - Variable Cost per Customer)
```

| Metric | Value |
|---|---|
| Monthly fixed costs | $X |
| Revenue per customer (ARPU) | $Y/mo |
| Variable cost per customer | $Z/mo |
| Contribution margin | $Y - $Z |
| Customers needed to break even | X / (Y - Z) |
| Months to break even (moderate scenario) | [estimate] |

### 3E. Return on Investment (ROI)

| Metric | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Total investment to date | | | |
| Cumulative revenue | | | |
| Net position | | | |
| ROI % | | | |

### 3F. Funding Assessment

Based on the financial model, assess:
- **Can this be bootstrapped?** (revenue covers costs before savings run out)
- **Does this need external funding?** If so, how much and what type?
  - Pre-seed ($25K-$250K): angel investors, accelerators
  - Seed ($250K-$2M): institutional seed funds
  - Series A ($2M-$15M): VCs (requires demonstrated traction)
- **Is this a lifestyle business or a venture-scale opportunity?**
  - Lifestyle: $100K-$1M ARR ceiling, owner-operated, profitable early
  - Venture: $10M+ ARR potential, requires hypergrowth, winner-take-most market

---

## Phase 4 — Legal & Regulatory Feasibility

This phase identifies legal requirements, risks, and compliance obligations.

### 4A. Business Structure & IP

| Question | Assessment |
|---|---|
| Recommended business entity | (LLC / C-Corp / S-Corp / Sole Prop — and why) |
| IP protection needed | (patents / trade secrets / copyright / trademark) |
| Open source considerations | (if applicable: license choice, CLA needs, dual licensing) |
| Terms of Service required? | Yes / No — complexity level |
| Privacy Policy required? | Yes / No — complexity level |

### 4B. Regulatory Compliance

Identify all applicable regulations based on:
- **Data handled**: Personal data (GDPR, CCPA), financial data (PCI-DSS, SOX),
  health data (HIPAA), children's data (COPPA), educational data (FERPA)
- **Industry**: Fintech (licensing), healthcare (FDA), legal (bar requirements)
- **Geography**: US federal, US state-specific, EU, UK, international
- **Platform rules**: App Store guidelines, Google Play policies, AWS AUP

| Regulation | Applies? | Impact | Compliance Cost | Timeline |
|---|---|---|---|---|
| GDPR | | | | |
| CCPA/CPRA | | | | |
| PCI-DSS | | | | |
| HIPAA | | | | |
| SOC 2 | | | | |
| App Store Guidelines | | | | |
| [industry-specific] | | | | |

### 4C. Legal Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Patent infringement | | | [prior art search results] |
| Trademark dispute | | | [from brand clearance in 1E] |
| Data breach liability | | | [security measures] |
| Regulatory non-compliance | | | [compliance plan] |
| Terms of service disputes | | | [standard terms] |
| Open source license conflicts | | | [license audit] |

### 4D. Legal Budget & Timeline

Estimate legal costs for launch readiness:

| Item | DIY Cost | Lawyer Cost | Priority |
|---|---|---|---|
| Entity formation | $50-$500 | $500-$2,000 | MUST |
| Terms of Service | $0 (template) | $1,000-$3,000 | MUST |
| Privacy Policy | $0 (template) | $500-$2,000 | MUST |
| Trademark filing | $250-$350 | $1,000-$2,000 | SHOULD |
| Patent search/filing | N/A | $5,000-$15,000 | MAYBE |
| Compliance audit | N/A | $3,000-$20,000 | [depends] |

---

## Phase 5 — Operational Feasibility

This phase assesses whether the founder/team can realistically build, launch, and
sustain this product.

### 5A. Team Assessment

| Role | Needed? | Available? | Gap? | Solution |
|---|---|---|---|---|
| Technical founder / lead developer | | | | |
| Designer (UI/UX) | | | | |
| Marketing / growth | | | | |
| Sales (if B2B) | | | | |
| Customer support | | | | |
| DevOps / infrastructure | | | | |
| Legal / compliance | | | | |

### 5B. Operational Requirements

What must be in place to run this product post-launch?

| Requirement | Complexity | Current Readiness |
|---|---|---|
| Customer support channel | LOW / MED / HIGH | Ready / Needs Setup / Not Started |
| Monitoring & alerting | | |
| Billing & invoicing | | |
| Onboarding flow | | |
| Documentation | | |
| Backup & disaster recovery | | |
| Incident response process | | |
| Update/deploy pipeline | | |

### 5C. Scalability Assessment

At what user counts do operations fundamentally change?

| Users | Operational Impact | Action Required |
|---|---|---|
| 1-100 | Founder handles everything | [current state] |
| 100-1,000 | Support volume becomes significant | [hire support / build self-serve] |
| 1,000-10,000 | Infrastructure scaling needed | [dedicated DevOps / managed services] |
| 10,000+ | Team structure required | [multiple hires, process formalization] |

### 5D. Founder Capacity Assessment

Be honest about bandwidth:
- Is this a full-time commitment or nights-and-weekends?
- How many hours/week can the founder realistically dedicate?
- What's the opportunity cost? (current job salary × time investment)
- Is there a financial runway? (months of savings to support no/low income)
- What's the burnout risk if this takes 2x longer than expected?

---

## Phase 6 — Schedule & Timeline Feasibility

This phase determines whether the project can be completed within a reasonable
timeframe and identifies critical path dependencies.

### 6A. Project Timeline

Estimate a realistic timeline with milestones:

| Phase | Duration | Milestone | Dependencies |
|---|---|---|---|
| Research & Planning | [weeks] | PRD complete, tech decisions finalized | None |
| Design | [weeks] | UI/UX mockups approved | PRD |
| MVP Development | [weeks] | Core features working, deployable | Design |
| Alpha Testing | [weeks] | Internal testing complete, critical bugs fixed | MVP |
| Beta / Early Access | [weeks] | External users testing, feedback collected | Alpha |
| v1.0 Launch | [weeks] | Public launch, marketing push | Beta |
| Post-Launch Iteration | [ongoing] | Feature expansion based on feedback | v1.0 |

### 6B. Critical Path Analysis

Identify the **longest dependency chain** — this is the minimum calendar time to launch:

```
[Critical path: A → B → C → D = X weeks minimum]
```

Identify **parallelizable work** that can happen simultaneously:
- Design + backend development
- Legal setup + development
- Marketing prep + beta testing

### 6C. Timeline Risk Factors

| Risk | Impact on Timeline | Likelihood | Mitigation |
|---|---|---|---|
| Scope creep | +2-8 weeks | HIGH | Strict MVP definition |
| Technical unknowns | +1-4 weeks | MEDIUM | Spike/prototype early |
| Third-party dependency delays | +1-2 weeks | LOW | Identify alternatives |
| Founder availability changes | +2-12 weeks | [depends] | Buffer in schedule |
| Hiring delays (if needed) | +4-8 weeks | MEDIUM | Start recruiting early |

### 6D. Schedule Verdict

Rate schedule feasibility:

**FEASIBLE** — Timeline is realistic given team, scope, and resources
**TIGHT** — Achievable but requires focused execution and no major setbacks
**AT RISK** — Timeline is aggressive; recommend extending or reducing scope
**INFEASIBLE** — Cannot be done in the proposed timeframe; recommend re-scoping

If AT RISK or INFEASIBLE, provide specific recommendations:
- What to cut from MVP to hit the timeline
- What to delay to a v1.1 release
- How much more time is needed for the full vision

---

## Phase 7 — Pricing & Go-to-Market Strategy

This phase applies the full pricing framework from the software valuation methodology.
It builds on the customer personas, competitive landscape, and financial model from
earlier phases.

### 7A. Demand Curve Analysis

Using personas from Phase 1D, sketch the demand curve:

| Price Point | Likely Buyers | Estimated Revenue |
|---|---|---|
| Free | All personas | $0 |
| $X (low) | Most personas | $X x N |
| $Y (mid) | Some personas | $Y x M |
| $Z (high) | Premium/enterprise only | $Z x P |
| $W (too high) | Nobody | $0 |

Identify the **revenue-maximizing price band**.

### 7B. Pricing Model Selection

Evaluate each model for fit (score as HIGH / MEDIUM / LOW):

| Model | Fit | Rationale |
|---|---|---|
| One-time perpetual license | | |
| Subscription (monthly/annual) | | |
| Freemium (free + paid upgrade) | | |
| Usage-based / metered | | |
| Gillette (razor/blade) | | |
| Open core (OSS + commercial) | | |
| Consulting / services wrapper | | |
| Marketplace / transaction fee | | |

**RECOMMENDATION**: State the single best model (or hybrid) with rationale.

### 7C. Tier / Versioning Strategy

| Tier Name | Target Persona | Key Differentiators | Suggested Price |
|---|---|---|---|
| Free / Community | | | $0 |
| Starter / Indie | | | $X |
| Pro / Team | | | $Y |
| Enterprise | | | $Z or "Contact us" |

### 7D. Purchasing Threshold Analysis

| Threshold | Typical Rule | Product's Position |
|---|---|---|
| < $10 | Personal card, no approval | |
| $10-$50 | Personal card, may expense | |
| $50-$999 | Boss's card, verbal OK | |
| $1,000-$4,999 | Formal approval required | |
| $5,000-$24,999 | Department head approval | |
| $25,000+ | CEO / board visibility | |

### 7E. Price Signaling Analysis

What does the proposed price communicate about the product?
- Does it signal quality, accessibility, or "toy"?
- Does it align with the brand positioning?
- Does it match customer expectations for this category?

### 7F. Bundling Opportunities

Identify natural bundles:
- Multiple modules or tools within the product
- Companion products (templates, presets, integrations)
- Third-party partnerships for "pro kit" offerings

### 7G. Network Effects Check

Does this product have network effects?
- **If YES**: Free pricing at launch recommended to hit tipping point. Monetize post-adoption.
- **If NO**: Standard demand-curve pricing. Don't give away value unnecessarily.

### 7H. Piracy / Cracking Risk Assessment

For desktop/offline products:
- Is piracy a realistic risk?
- If yes: price at a point where paying is easier than pirating
- For most indie software, the Apple Music strategy beats the Adobe strategy

### 7I. Launch Pricing Strategy

| Timeframe | Strategy | Price | Rationale |
|---|---|---|---|
| Pre-launch | | | |
| Day 1 | | | |
| Month 3 | | | |
| Month 6 | | | |
| Month 12 | | | |

Include early adopter pricing, introductory offers, and price escalation plan.

### 7J. Marketing Strategy

**Perceived Value Enhancement**:
- Specific tactics for this product (personality, tribe, demos, content, founder visibility)

**Reference Point Management**:
- Which comparisons to encourage vs. avoid

**Channel Strategy**:
- How to sell: web self-serve, marketplace, direct sales, OSS community, app stores

**Key Messaging Pillars**:
- 3 messages that justify the price and differentiate from alternatives

---

## Phase 7K � Open Source & Community Strategy

If the founder's goals include building developer credibility, GitHub traction, or
community-driven growth (not just revenue), include this section. Skip if the product
is purely commercial/closed-source.

### 7K-1. Open Source Positioning

Assess whether open-sourcing makes strategic sense:

| Factor | Assessment |
|---|---|
| Is the product value in code or in data/network? | Code = OSS friendly; Data/Network = keep proprietary |
| Does the product benefit from community contributions? | More adapters/integrations = YES |
| Is there a hosted-service monetization path? | Free code + paid hosting = viable OSS business |
| Does the founder want GitHub credibility? | If yes, OSS is the fastest path |

**Key insight**: The most-starred repos ship frameworks and toolkits, not finished apps.
If the product can be restructured as a pluggable toolkit with a reference implementation,
it will attract more contributors and stars than a monolithic app.

### 7K-2. Architecture for Contribution

Propose a repo structure that makes contributing easy:

- **Pluggable adapters** � let contributors add support for new services without touching core code
- **Clear interfaces** � TypeScript interfaces or similar contracts that define adapter requirements
- **Good first issue surface area** � identify 10+ issues that a new contributor could tackle
- **Standalone packages** � extract reusable logic into npm/pip/crate packages for wider adoption

### 7K-3. GitHub Traction Playbook

Outline a concrete launch and growth plan:

**Pre-launch (before v1.0):**
- Best-in-class README (architecture diagram, screenshots, Why this exists, quick start)
- CONTRIBUTING.md with good first issues guidance
- LICENSE (MIT or Apache 2.0 � lowest barrier)
- Issue templates for common contribution types
- CI pipeline (lint, type-check, build, test)

**Launch (week 1):**
- Show HN post
- Reddit posts to relevant communities (r/opensource, r/webdev, domain-specific subs)
- Product Hunt submission (positioned as a developer tool)
- Build-in-public social media thread

**Growth (month 1-3):**
- Maintain 5-10 good first issue labels at all times
- Respond to all issues and PRs within 48 hours
- Monthly changelog / state-of-the-project updates
- Community channel (Discord, GitHub Discussions)

**Ecosystem (month 3-6):**
- Publish standalone packages extracted from the project
- Hacktoberfest participation (if timing aligns)
- Built with [project] showcase
- Conference talks or blog posts about the architecture

### 7K-4. Browser Extension / CLI Strategy (if applicable)

If the product is web-based, assess whether a browser extension or CLI would increase
organic discovery and GitHub traction:

- Browser extensions have built-in distribution via Chrome Web Store
- CLI tools are highly shareable in developer communities
- Both can use the same core library, proving the pluggable architecture works

### 7K-5. Community Health Metrics

| Metric | Target (Month 3) | Target (Month 6) |
|---|---|---|
| GitHub stars | 100-300 | 500-1,000 |
| Contributors | 5-10 | 15-25 |
| Forks | 20-50 | 50-150 |
| PR merge time | <48 hours | <48 hours |
| Open good first issue count | 5-10 (always) | 5-10 (always) |

### 7K-6. What to Avoid

- Do not gate OSS features behind a paid tier in the repo
- Do not ignore issues/PRs � a responsive small project beats a neglected popular one
- Do not over-engineer before launch � ship 1-2 adapters, let the community build the rest
- Do not put AI in the repo name for hype � lead with the problem, not the tech

## Phase 8 — Risk Synthesis & Go/No-Go Assessment

This phase consolidates all risks from previous phases and delivers the final verdict.

### 8A. Consolidated Risk Register

Gather the top risks from every phase into a single register:

| # | Risk | Source Phase | Likelihood | Impact | Severity | Mitigation |
|---|---|---|---|---|---|---|
| 1 | | | H/M/L | H/M/L | CRITICAL/HIGH/MED/LOW | |
| 2 | | | | | | |
| ... | | | | | | |

Severity scoring:
- **CRITICAL**: Could kill the project entirely
- **HIGH**: Major impact on success; requires active mitigation
- **MEDIUM**: Manageable but should be planned for
- **LOW**: Minor; accept and monitor

### 8B. SWOT Analysis

| | Helpful | Harmful |
|---|---|---|
| **Internal** | **Strengths**: [list] | **Weaknesses**: [list] |
| **External** | **Opportunities**: [list] | **Threats**: [list] |

### 8C. Feasibility Scorecard

Rate each dimension on a 1-5 scale:

| Dimension | Score (1-5) | Key Finding |
|---|---|---|
| Market Feasibility | | [one-line summary] |
| Technical Feasibility | | [one-line summary] |
| Financial Feasibility | | [one-line summary] |
| Legal Feasibility | | [one-line summary] |
| Operational Feasibility | | [one-line summary] |
| Schedule Feasibility | | [one-line summary] |
| Pricing Viability | | [one-line summary] |
| **Overall Score** | **/5** | |

Scoring guide:
- **5**: Excellent — strong position, low risk
- **4**: Good — favorable with minor concerns
- **3**: Moderate — viable but with notable risks
- **2**: Challenging — significant obstacles to overcome
- **1**: Poor — fundamental issues that may be disqualifying

### 8D. Go / No-Go Recommendation

Deliver one of four verdicts:

**GO** — The idea is viable across all dimensions. Proceed with confidence.
Provide a recommended first action.

**GO WITH CONDITIONS** — The idea is viable but specific conditions must be met first.
List the conditions explicitly (e.g., "viable only if you can hire a backend developer
within 60 days" or "viable only if legal review confirms no IP conflict").

**PIVOT RECOMMENDED** — The core idea has merit but the current approach has fatal
flaws. Suggest specific pivots (different market segment, different delivery model,
different pricing, different technical approach).

**NO-GO** — The idea is not viable in its current form. Explain which dimensions
fail and why. If there's a path to viability, describe it. If not, say so directly.

---

## Phase 9 — Report Generation

Generate a complete **Market Feasibility Report** as a structured Markdown document.

### Report Structure

```
# Market Feasibility Report
## [Product Name]
Generated: [date]

---

## Executive Summary
[5-7 sentence overview: what the idea is, the key findings across all dimensions,
the overall feasibility score, and the go/no-go recommendation. If there are critical
risks (brand name RED, legal blockers, etc.), flag them here prominently.]

---

## Feasibility Scorecard
[Scorecard table from 8C — placed early for quick scanning]

---

## Idea Profile
[Extraction checklist from 0B + stated assumptions from 0C]

---

## Market & Commercial Feasibility
### Problem Validation
[From 1A]
### Market Sizing
[TAM/SAM/SOM from 1B]
### Competitive Landscape
[Competitor matrix from 1C]
### Customer Segments
[Personas from 1D]
### Brand Name Clearance
[Full clearance report from 1E]

---

## Technical Feasibility
### Requirements Analysis
[From 2A]
### Recommended Stack
[From 2B]
### Technical Risks
[From 2C]
### Build vs. Buy
[From 2D]
### MVP Definition
[From 2E]

---

## Financial Feasibility
### Development Costs
[From 3A]
### Operating Costs
[From 3B]
### Revenue Projections
[From 3C]
### Break-Even Analysis
[From 3D]
### ROI Projections
[From 3E]
### Funding Assessment
[From 3F]

---

## Legal & Regulatory Feasibility
### Business Structure & IP
[From 4A]
### Regulatory Compliance
[From 4B]
### Legal Risks
[From 4C]
### Legal Budget
[From 4D]

---

## Operational Feasibility
### Team Assessment
[From 5A]
### Operational Requirements
[From 5B]
### Scalability Plan
[From 5C]
### Founder Capacity
[From 5D]

---

## Schedule Feasibility
### Project Timeline
[From 6A]
### Critical Path
[From 6B]
### Timeline Risks
[From 6C]
### Schedule Verdict
[From 6D]

---

## Pricing & Go-to-Market Strategy
### Demand Curve Analysis
[From 7A]
### Pricing Model Recommendation
[From 7B]
### Tier Structure
[From 7C]
### Launch Pricing Strategy
[From 7I]
### Marketing Strategy
[From 7J]
### Bundling Opportunities
[From 7F]

---

## Open Source & Community Strategy (if applicable)
### Open Source Positioning
[From 7K-1]
### Architecture for Contribution
[From 7K-2]
### GitHub Traction Playbook
[From 7K-3]
### Browser Extension / CLI Strategy
[From 7K-4]
### Community Health Metrics
[From 7K-5]

---

## Risk Analysis
### Consolidated Risk Register
[From 8A]
### SWOT Analysis
[From 8B]

---

## Recommendation
### Verdict: [GO / GO WITH CONDITIONS / PIVOT RECOMMENDED / NO-GO]
[Detailed rationale — reference specific findings from each phase]

### Conditions (if applicable)
[Numbered list of conditions that must be met]

### Recommended Next Steps
[Ordered action list: what to do first, second, third — make these concrete and
time-bound, not vague]

---

## Davidson Pricing Checklist
[Completed checklist tailored to this product]

---

## Appendix: Assumptions & Methodology
[All assumptions declared in Phase 0C + any additional assumptions made during analysis]
[Note which findings are based on web research vs. estimation vs. industry benchmarks]
```

---

## Output Delivery

After generating the report:

1. Save to the current working directory as `feasibility-report-[product-name].md`
2. Present the file to the user
3. Provide a verbal summary of the **top 5 most important findings** — keep it concise,
   not a wall of text
4. State the **go/no-go recommendation** clearly
5. Offer to go deeper on any specific section

---

## Quality Rules

- **Never fabricate market data or competitor prices** — if web search isn't available,
  say so and mark the data as "[NEEDS VERIFICATION — web search unavailable]". The user
  must fill in real data.
- **Anchor every recommendation to a specific observation**. "We recommend subscription
  pricing because the competitive landscape shows all 5 competitors use monthly SaaS
  models" — not generic advice.
- **Flag when an idea is too vague to assess** — if the user's description is a single
  sentence with no specifics, say so directly: *"I need more detail to produce a useful
  feasibility study. Here's what I need to know: [list]."*
- **Be honest about viability** — a NO-GO verdict delivered clearly is more valuable than
  a watered-down GO that wastes months of the founder's life. Be direct but constructive.
- **Don't conflate enthusiasm with feasibility** — an exciting idea can still be
  infeasible. A boring idea can be highly viable. Assess objectively.
- **Apply the "practice trumps theory" principle** — always end with concrete next steps,
  not just frameworks and analysis.
- **Separate facts from estimates** — clearly label which numbers are researched vs.
  estimated. Use ranges rather than false precision.
- **Consider the user's context** — a bootstrapped solo founder gets different advice than
  a funded team. Tailor operational and financial assessments accordingly.

---

## Reference Frameworks Embedded In This Skill

This skill applies the following frameworks:

1. **Feasibility study methodology** — seven-dimension viability assessment (market,
   technical, financial, legal, operational, schedule, pricing)
2. **TAM/SAM/SOM market sizing** — bottom-up and top-down market estimation
3. **Demand curve analysis** — price x volume = revenue; find the revenue-maximizing rectangle
4. **Perceived vs. objective value** — customers pay for what they *think* something is worth
5. **Reference point theory** — anchor comparisons to favorable benchmarks
6. **Versioning / price discrimination** — serve multiple WTP levels with tiered pricing
7. **Bundling math** — heterogeneous preferences unlock hidden revenue
8. **Network effects tipping point** — free pricing to drive adoption past critical mass
9. **Switching cost mitigation** — economic and psychological barriers in pricing
10. **Purchasing threshold awareness** — price relative to organizational approval thresholds
11. **Price as signal** — the number you charge communicates brand quality and intent
12. **Value-based pricing** — price to the benefit delivered, not the cost incurred
13. **SWOT analysis** — internal strengths/weaknesses, external opportunities/threats
14. **Critical path analysis** — identify minimum timeline and parallelizable work
15. **Break-even analysis** — fixed costs / contribution margin = customers needed
