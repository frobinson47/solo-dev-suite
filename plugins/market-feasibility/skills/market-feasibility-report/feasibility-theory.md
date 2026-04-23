# Feasibility Study & Pricing Theory Reference
## Distilled from established frameworks + Neil Davidson's "Don't Just Roll the Dice"

This reference is bundled with the market-feasibility-report skill. Claude Code should
consult it during analysis phases to ensure recommendations are grounded in established
methodology.

---

## Part I: Feasibility Study Fundamentals

### What Is a Feasibility Study?

A feasibility study is a structured investigation into whether a proposed project is
**worth pursuing** before significant resources are committed. It answers one question:
*"Should we build this?"*

The answer is not binary. The output is a **risk-adjusted recommendation** across
multiple dimensions, with clear conditions and next steps.

### The Seven Dimensions of Feasibility

Every software product idea should be evaluated across these dimensions. Weakness in
any single dimension can kill a project — but each dimension has different remediation
paths.

**1. Market / Commercial Feasibility**
- Is there real demand for this product?
- Is the market large enough to sustain a business?
- Can you differentiate from existing solutions?
- *Kill signal*: No one has the problem, or the problem is already perfectly solved

**2. Technical Feasibility**
- Can this be built with available technology?
- Does the team have the skills to build it?
- Are there unsolved technical challenges that block the core value proposition?
- *Kill signal*: Required technology doesn't exist, or complexity exceeds team capacity

**3. Financial / Economic Feasibility**
- Can this product generate more revenue than it costs to build and operate?
- How much capital is needed before revenue starts?
- When does the project break even?
- *Kill signal*: Unit economics are structurally negative (costs per customer exceed
  lifetime revenue per customer with no path to improvement)

**4. Legal / Regulatory Feasibility**
- Are there laws, regulations, or compliance requirements that affect this product?
- Can the product operate legally in its target markets?
- What is the intellectual property landscape?
- *Kill signal*: Product is illegal in target market, or compliance costs exceed revenue potential

**5. Operational Feasibility**
- Can the founder/team actually deliver and sustain this product?
- What operational infrastructure is needed post-launch?
- Does the team have the bandwidth, skills, and organizational capacity?
- *Kill signal*: Team lacks critical skills with no viable path to acquire them

**6. Schedule / Timeline Feasibility**
- Can the product be built within a reasonable timeframe?
- Is there a market window that must be hit?
- What's the critical path and where are the bottlenecks?
- *Kill signal*: Market window closes before product can launch, or time-to-market
  exceeds founder's financial runway

**7. Pricing / Monetization Feasibility**
- Can the product be priced in a way that sustains the business?
- Is there willingness to pay at a level that covers costs?
- Does the pricing model match the product's delivery mechanism and market expectations?
- *Kill signal*: Target market expects free, and no viable monetization path exists

### Common Feasibility Mistakes

**1. Confirmation Bias**
Founders fall in love with their idea and unconsciously seek evidence that supports it
while dismissing contradictory data. The feasibility study must actively seek disconfirming
evidence. Ask: "What would make this fail?" not just "Why will this succeed?"

**2. Underestimating Time and Cost**
Software projects routinely take 2-3x longer and cost 1.5-2x more than estimated.
Apply a **realism multiplier** to all estimates:
- Experienced team, well-defined scope: 1.5x
- Mixed experience, moderately defined: 2x
- New team or ambiguous scope: 3x

**3. Ignoring Operational Costs**
Building the product is the exciting part. Running it — support, infrastructure, billing,
compliance, bug fixes — is the expensive part. A product that costs $50K to build might
cost $5K/month to operate. Factor this in.

**4. Skipping Legal**
"We'll deal with legal later" has killed many startups. GDPR fines, patent trolls,
trademark disputes, and regulatory non-compliance are real and expensive. Better to
discover blockers in a feasibility study than after launch.

**5. Overestimating Market Size**
"The global CRM market is $50 billion, so if we capture just 1%..." — this reasoning
is almost always wrong. Use bottom-up estimation (count actual reachable customers)
rather than top-down market share fantasies.

---

## Part II: Market Analysis Framework

### TAM / SAM / SOM Explained

- **TAM (Total Addressable Market)**: Everyone who could theoretically use this product,
  globally, at any price. This is the "dream number" and is almost never achievable.

- **SAM (Serviceable Addressable Market)**: The subset of TAM you can actually reach
  with your distribution, geography, language, and product capabilities. This is the
  realistic upper bound.

- **SOM (Serviceable Obtainable Market)**: The subset of SAM you can realistically
  capture in the first 1-3 years given your resources, brand, and competitive position.
  This is your planning number.

**Rule of thumb**: SOM is typically 1-5% of SAM for a new entrant. If your business
plan requires >5% market capture in year 1, your plan is probably wrong.

### Problem-Solution Fit Assessment

Not every real problem justifies a software product. The problem must be:
1. **Frequent** — experienced regularly, not once a year
2. **Painful** — costs real time, money, or frustration
3. **Recognized** — the target user knows they have this problem
4. **Underserved** — existing solutions are inadequate or nonexistent
5. **Monetizable** — people with this problem have budget to solve it

Score each criterion 1-5. A total below 15/25 suggests weak problem-solution fit.

### Competitive Moat Assessment

Long-term viability requires at least one defensible advantage:

| Moat Type | Description | Strength | Example |
|---|---|---|---|
| Network effects | More users = more value | Very strong | Slack, GitHub |
| Switching costs | Painful to leave | Strong | Salesforce, enterprise DB |
| Data advantage | Proprietary data improves product | Strong | Google Maps |
| Brand / trust | Reputation as the default choice | Moderate | Stripe |
| Technical IP | Patents, algorithms, trade secrets | Moderate | Algolia |
| Cost advantage | Can deliver cheaper than competitors | Weak (easily copied) | Budget hosting |
| First-mover | Got there first | Weak (easily eroded) | — |

Products with no moat will face constant price pressure and commoditization.

---

## Part III: Pricing Theory (from Davidson)

### Core Economics: The Demand Curve

Every software product has a demand curve: as price rises, fewer people buy. The key
insight is that **revenue = price x quantity**, and these trade off against each other.

| Price | Buyers | Revenue |
|---|---|---|
| $0 | Maximum | $0 |
| Low | Many | Low-Medium |
| Mid | Some | Often maximum |
| High | Few | Declining |
| Too high | None | $0 |

**The revenue-maximizing price is not where you sell the most units. It's where the
rectangle (price x quantity) under the demand curve is largest.**

### What Customers Are Actually Buying

Software buyers are not buying bits and bytes. They are buying:
- **Reassurance** — it will keep working, it will be maintained
- **Familiarity** — their colleagues already know it
- **Support** — someone will answer the phone
- **Future roadmap** — it won't be abandoned
- **A dream** — a better version of their workflow

**Implication for pricing**: Features alone don't justify price. The full product
ecosystem — docs, support, roadmap, community, reputation — does.

### Perceived Value vs. Objective Value

Customers do not rationally calculate ROI before buying. They have a **perceived value**
that may be higher or lower than the objective economic benefit.

- **Higher than objective**: CRM software (nearly half went unused per Gartner), lottery
  tickets (expected value < price but millions buy)
- **Lower than objective**: Developer tools that would pay for themselves in a week,
  but buyers can't justify it to their boss

**To change what someone pays, you must change their perception — not just the product.**

### Reference Points

Customers cannot price things in a vacuum. They anchor to **reference points**:
- Competitor prices
- Category norms
- Your other products
- Their own previous purchases

**Control your reference points aggressively.** If your product is premium, point to
higher-priced alternatives, not lower-priced ones.

### How to Increase Perceived Value

1. **Increase objective value** — new features drive revenue most reliably
2. **Give it a personality** — stand for something specific
3. **Link to founder expertise** — credibility signals transfer to product
4. **Make people love it** — build a tribe, not just a user base
5. **Provide better service** — small companies can outperform large ones here
6. **Build identity** — products as badges can charge identity premiums
7. **Invoke your effort** — effort signals = legitimacy
8. **Use psychological pricing** — $995 vs $1,000 works

### Pricing Pitfalls

**Price Wars**: Dangerous. Incumbents with deeper pockets will absorb losses.
Minimize price competition visibility.

**Fairness**: Customers have strong fairness instincts. Violating them causes backlash
beyond just losing the sale.

**Piracy**: High piracy rates signal a market failure — price exceeds WTP. For most
indie software, price where paying is easier than pirating.

**Sunk Cost Fallacy**: Development cost is irrelevant to pricing. It's sunk. Price
to what customers will pay.

### Versioning

Sell the same core product at different price points to different segments.

Axes: feature, availability, demographic, geography, industry, platform.

**The "Jumbo" Effect**: Adding a more expensive tier shifts buyers toward the tier below
it. A $249 tier makes the $99 tier feel like the safe middle choice.

**Warning**: If tier differences are confusing, buyers flee to extremes or defer entirely.
Keep differences simple — one axis of difference per tier step.

### Bundling

Different buyers value different components differently. Bundling captures revenue
from heterogeneous preferences that individual pricing misses.

**Pitfall**: Bundled items get consumed less. Be explicit about each component's
individual value even within the bundle.

### Network Effects

Products where each additional user increases value for all users have a **tipping
point**. Price free before the tipping point to maximize adoption. Monetize after.

Pricing too early in a network-effect product slows adoption below the tipping point
and the user base shrinks back toward zero.

### Price as Signal

- Premium price: signals quality and seriousness
- Discount price: signals accessibility, risks "toy" perception
- Matching competitors exactly: "me too" — needs differentiation
- Free: network-effect strategy or "haven't figured out monetization"

The signal must align with brand reality.

---

## Part IV: Financial Modeling for Feasibility

### Unit Economics

The single most important financial question: **Do you make money per customer?**

```
LTV (Lifetime Value) = ARPU x Average Customer Lifespan
CAC (Customer Acquisition Cost) = Total Marketing Spend / New Customers Acquired
LTV:CAC Ratio = LTV / CAC
```

- LTV:CAC > 3:1 — healthy business
- LTV:CAC 1:1 to 3:1 — viable but tight, needs optimization
- LTV:CAC < 1:1 — losing money on every customer; not viable at scale

### Break-Even Analysis

```
Break-even customers = Monthly Fixed Costs / (ARPU - Variable Cost per Customer)
Break-even months = Total Investment / Monthly Net Revenue (at steady state)
```

For feasibility purposes, if break-even requires more customers than your realistic
SOM, or more months than your financial runway, the project is financially infeasible
in its current form.

### The Bootstrapping Test

A project passes the bootstrapping test if:
1. MVP can be built within the founder's budget (savings or revenue from other work)
2. Monthly operating costs are below $500 until revenue begins
3. Revenue covers operating costs within 6 months of launch
4. The founder can sustain themselves financially for the entire timeline

If all four conditions are met, the project can be bootstrapped. If any fail, external
funding or significant scope reduction is needed.

---

## Part V: Risk Assessment Framework

### Risk Scoring Matrix

| | Low Impact | Medium Impact | High Impact |
|---|---|---|---|
| **High Likelihood** | MEDIUM | HIGH | CRITICAL |
| **Medium Likelihood** | LOW | MEDIUM | HIGH |
| **Low Likelihood** | LOW | LOW | MEDIUM |

### Risk Categories for Software Projects

1. **Market risk** — demand doesn't materialize, timing is wrong
2. **Technical risk** — can't build it, performance issues, scaling challenges
3. **Financial risk** — runs out of money, unit economics don't work
4. **Legal risk** — regulatory blockers, IP disputes, compliance costs
5. **Team risk** — key person leaves, can't hire, skill gaps
6. **Competitive risk** — incumbent copies your features, funded competitor emerges
7. **Platform risk** — dependency on a platform that changes rules (App Store, AWS, API)

### The Pre-Mortem Exercise

Before concluding the feasibility study, run a mental pre-mortem:

*"It's 12 months from now and this project has failed. What went wrong?"*

List the 3 most likely failure scenarios and assess whether the feasibility study
has adequately addressed each one. If not, go back and strengthen that section.
