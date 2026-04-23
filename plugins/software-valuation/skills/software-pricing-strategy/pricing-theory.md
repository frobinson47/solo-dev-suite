# Software Pricing Theory Reference
## Distilled from "Don't Just Roll the Dice" by Neil Davidson

This reference is bundled with the software-pricing-strategy skill. Claude Code should
consult it during Phase 3 (Framework Application) to ensure recommendations are grounded
in established pricing science.

---

## Core Economics: The Demand Curve

Every software product has a demand curve: as price rises, fewer people buy. The key
insight is that **revenue = price × quantity**, and these trade off against each other.

| Price | Buyers | Revenue |
|---|---|---|
| $0 | Maximum | $0 |
| Low | Many | Low |
| Mid | Some | Often maximum |
| High | Few | Declining |
| Too high | None | $0 |

**The revenue-maximizing price is not where you sell the most units. It's where the
rectangle (price × quantity) under the demand curve is largest.**

In practice, you don't know the exact curve shape. Use persona-based WTP estimates to
approximate it, then test and iterate.

---

## What Is Your Product, Really?

Software buyers are not buying bits and bytes. They are buying:
- **Reassurance** — it will keep working, it will be maintained
- **Familiarity** — their colleagues already know it
- **Support** — someone will answer the phone
- **Future roadmap** — it won't be abandoned
- **A dream** — a better version of their workflow

Example: Sage accounting software dominated the UK market despite having a terrible UI.
Why? Because Sage understood they were selling *reassurance and accountant familiarity*,
not software quality. 40,000 support calls per day proved it.

**Implication for pricing**: Features alone don't justify price. The full product
ecosystem — docs, support, roadmap, community, reputation — does.

---

## Perceived Value vs. Objective Value

Customers do not rationally calculate ROI before buying. They have a **perceived value**
that may be higher or lower than the objective economic benefit.

- **Higher than objective**: CRM software (2003 Gartner study: nearly half went unused),
  lottery tickets ($5 ticket has expected value of $3 but millions buy)
- **Lower than objective**: Developer tools that would pay for themselves in a week, but
  buyers can't justify it to their boss

**To change what someone pays, you must change their perception — not just the product.**
Marketing is the mechanism for closing the gap between objective and perceived value.

---

## Reference Points: What Customers Compare You To

Customers cannot price things in a vacuum. They anchor to **reference points**:
- Competitor prices
- Category norms
- Your other products (signposts)
- Their own previous purchases

**Implication**: Control your reference points aggressively.
- If your to-do app costs $200 when the market is $100, differentiate it so direct
  comparison is impossible, then point to $300 productivity suites, not other to-do apps.
- If your product is new category with no comparators, you can **define** the reference
  point. Microsoft set DOS at $50 in 1982 — this became "what an OS costs" for years.
- Your cheapest product acts as a signpost for your most expensive one. Price your
  simple tool at $25 and customers will trust your $300 tool is fair.

---

## How to Increase Perceived Value (Specific Tactics)

1. **Increase objective value** — new features drive revenue more reliably than any
   other lever. As Joel Spolsky noted, nothing at Fog Creek increased revenue more than
   new versions with more features.

2. **Give it a personality** — 37signals didn't build the best PM software, but it stood
   for something: uncompromising simplicity. That stance itself has value.

3. **Link product to founder expertise** — Peter Norton put his face on everything. His
   arms-crossed photo signaled credibility and expertise. "This person is an expert;
   therefore I can trust this software."

4. **Make people love it, not just use it** — DeWALT drove to NASCAR races and gave out
   pulled pork sandwiches. They built a *tribe*. Amateurs paid $400 for professional drills
   because they wanted to belong to the "pro" group.

5. **Provide better service than your bigger competitors can** — small companies can
   respond to support tickets personally. Large companies cannot. That's a real advantage.

6. **Build a tribe** — products that are a badge of identity can charge identity premiums.
   Apple is the canonical example. The tribe people belong to shapes what they'll pay.

7. **Invoke your effort** — remind buyers of the years invested. Bill Gates's 1976 open
   letter to Homebrew Club hobbyists referenced the $40,000+ in computer time spent
   developing BASIC. Effort signals = legitimacy.

8. **Use psychological pricing** — $1995 vs $2000. Works. $995 vs $1000. Works. The
   effect is real and well-documented.

---

## Pricing Pitfalls

### Price Wars
Starting a price war is dangerous. Laker Airways undercut BA and Pan Am in 1977 with
$238.25 transatlantic tickets. Five years later it was bankrupt. Incumbents with deeper
pockets will absorb losses to defend market share.

**Rule**: If you compete on price, minimize visibility. Target marginal customers quietly.
Don't trumpet how you're going to "destroy" the incumbent.

### Fairness
Customers have a strong and often irrational sense of fairness. Violate it and they
won't just leave — they'll tell everyone.

Example: E-book prices equal to paperback prices feel *unfair* even if the economic
value is identical. Customers feel the marginal cost of electrons is near zero, so the
same price for electrons and paper is unjust.

**Rule**: If your pricing feels unfair to a reasonable person, it probably is. Fix it
before it becomes a support issue or public complaint.

### Piracy as Market Signal
High piracy rates signal a **market failure** — your price is above the willingness-to-pay
of a significant segment. Two possible strategies:

1. **Adobe strategy**: Keep prices high, let pirates aspire to ownership. Works when brand
   status is high and conversion eventually happens.
2. **Apple music strategy**: Recognize piracy as unsatisfied demand. Price low, make legal
   access easier than illegal access.

Choose based on your brand positioning and customer demographics.

### Sunk Cost Fallacy in Pricing
Your development cost is **irrelevant** to your pricing. It's gone. Sunk. What matters is
what customers are willing to pay. A product that cost $1M to build but solves a $50 problem
for most buyers should be priced around $50.

This is psychologically hard for founders but economically important.

---

## Versioning: Price Discrimination Done Right

**Versioning** is the mechanism of selling the same core product at different price points
to different segments based on willingness to pay.

### Versioning Axes
- **By feature**: Standard vs. Pro vs. Enterprise (Visual Studio: Free → $10,939)
- **By availability**: Early access vs. stable release (hardback vs. paperback)
- **By demographic**: Student pricing, nonprofit pricing
- **By geography**: Different prices per region (do this carefully — it triggers fairness concerns)
- **By industry**: Legal edition, healthcare edition, education edition
- **By platform**: Mac vs. Windows vs. Enterprise (can charge differently)

### The "Jumbo" Effect
Adding a more expensive tier shifts buyer behavior toward the tier *below* it, even if
nobody buys the expensive tier. Adding a "Jumbo" drink makes the "Large" drink feel
like the safe, reasonable middle choice.

**Corollary**: If you want to sell more of your $99 tier, add a $249 tier.

### When Versioning Backfires
If buyers **can't compare** the versions (too many confusing features), they flee to
extremes (cheapest or most expensive) or defer the purchase entirely. Microsoft Vista's
6-version lineup caused many buyers to simply buy a Mac or stick with XP.

**Rule**: Keep tier differences simple and easily communicable. One axis of difference
per tier step is ideal.

---

## Bundling: Unlocking Hidden Revenue

Bundling works because different buyers value different components differently. If Buyer A
values Product X at $400 and Product Y at $50, and Buyer B values them inversely,
selling each separately forces you to price at the lower valuation of each. Bundling at
$450 captures revenue from both buyers at once.

**Bundle pricing formula**:
```
Individual revenues: (lowest WTP for X × buyers) + (lowest WTP for Y × buyers)
Bundle revenue: (combined WTP for bundle × all buyers)
```
Bundle revenue is almost always higher when WTP is negatively correlated across buyers.

### Bundle Pitfall: Decoupling Consumption
When something is bundled, buyers consume less of it. Restaurant diners skip bundled
coffee more often than explicitly-priced coffee. For software: if buyers feel they got
something "for free" in a bundle, they're less likely to use it — and therefore less
likely to renew or buy an upgrade. Combat this by **being explicit about each component's
individual value** even within the bundle.

---

## Pricing Models Compared

| Model | Best For | Key Risk |
|---|---|---|
| One-time perpetual | Developer tools, desktop, offline | Revenue cliffs between versions |
| Annual subscription | SaaS, cloud, actively updated | Churn; must justify renewal value |
| Monthly subscription | High-frequency users, low-commitment entry | Higher churn, lower LTV |
| Freemium | Network effects, developer tools, high volume | Free tier cannibalizes paid |
| Usage-based | APIs, compute, storage | Bill shock causes anxiety and churn |
| Open core | Developer infra, databases | Community perceives enterprise tier as "hostageware" |
| Per-seat | Team tools, productivity apps | Licensing enforcement burden |
| Gillette (razor/blade) | Free delivery mechanism + paid consumption | Depends on ongoing usage to recoup |

### On Subscriptions
Monthly subscription payments are psychologically easier than large one-time payments.
People buy $30,000 cars on credit even at 20% interest because "it's only $400/month."
Use this. Annual subscriptions with monthly payment options often convert better than
either pure annual or pure monthly alone.

Health club data: monthly members use the club more consistently and stay longer than
annual fee members. More usage = more perceived value = more renewals. Design subscriptions
to encourage regular usage.

### The Boring Advice Is Usually Right
When choosing a pricing model: **be boring**. Choose the model your customers expect.
Red Gate's first product (Aardvark) charged per bug raised, calling units "cans of worms."
Customers hated it. After switching to per-user pricing, everything worked.

The clever, novel pricing model almost never beats the obvious one that matches
customer expectations.

---

## Network Effects and the Tipping Point

Products with network effects (each additional user makes the product more valuable to
all users) have a **tipping point** — a critical adoption mass past which growth
accelerates sharply.

Twitter hit its tipping point in early 2009. Before: slow linear growth. After: explosive.

**Implication**: If your product has meaningful network effects, pricing free at launch is
not generosity — it's strategy. Get to the tipping point as fast as possible. Then monetize.

If you price too early in a network-effect product, you slow adoption, fail to reach
the tipping point, and your user base shrinks back toward zero.

---

## What Your Price Says About You

Prices are never neutral signals. They communicate:

- **Premium price**: Quality, seriousness, enterprise-readiness
- **Discount price**: Accessibility — but risks "toy" perception in B2B markets
- **Copying competitor price exactly**: "Me too" — you need a better reason for buyers
  to choose you
- **Free**: Either network-effect land-grab or "we haven't figured out monetization yet"

**The signals your price sends must align with your brand reality.** McDonald's
launched the Arch Deluxe in 1996 — a "premium" burger at a 32-cent premium — spending
$200M on marketing. It flopped because the premium signal didn't match McDonald's brand
reality of cheap and convenient.

---

## The Davidson Pricing Checklist

Before finalizing any pricing decision, answer every question:

1. **Strategy**: Low price + high volume, or high price + low volume? Which fits your
   product, brand, and ops capacity?

2. **Product definition**: What are you *actually* selling? (Not just the software —
   the support, roadmap, community, reputation)

3. **Fairness test**: How will customers judge whether this price is fair?
   What reference points will they use?

4. **Customer profile**: How do they buy? Credit card impulse? IT procurement?
   What's their budget cycle? Monthly opex or annual capex?

5. **Competitor reaction**: If you undercut them, will they start a price war?
   If you price higher, will a new entrant undercut you?

6. **Sales model**: Web self-serve, inside sales, field sales, channel/reseller?
   Your cost of sale must be recoverable at your price point.

7. **Segmentation**: Can you version by feature, geography, demo, or industry?

8. **Bundling**: Can you combine products to serve multiple WTP levels simultaneously?

9. **Informed first price**: Pick a number. Any number is better than none. Get it
   broadly right, then iterate.

10. **Test and adjust**: Practice trumps theory. Ship the price, watch behavior,
    change what isn't working.

---

## The Most Important Rule

> "You're never going to know if you've chosen the exact right price or not, but you should
> experiment once you've set your initial price... The exact price almost doesn't matter —
> get it broadly right, don't screw up totally — and you can tweak it later."
> — Neil Davidson, *Don't Just Roll the Dice*

**An imperfect price that ships beats a perfect price that never gets set.**
