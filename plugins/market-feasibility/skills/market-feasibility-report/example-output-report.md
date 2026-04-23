# Market Feasibility Report
## FleetPulse — Fleet Maintenance Intelligence Platform
Generated: 2026-04-12
*This file is a reference example only — it shows Claude Code the expected output format.*

---

## Executive Summary

FleetPulse is a proposed SaaS platform that uses telematics data and predictive
analytics to help small-to-mid fleet operators (10-200 vehicles) schedule preventive
maintenance before breakdowns occur. The market opportunity is real: fleet maintenance
is a $30B+ US industry, and small operators are underserved by enterprise tools like
Fleetio and Samsara. Technical feasibility is strong — the core stack is well-understood
(React + Node + PostgreSQL + telematics APIs), though the predictive ML component
carries moderate risk. Financial projections show break-even at ~180 customers on a
$99/month plan, achievable within 12-18 months in the moderate scenario. The primary
risks are competitive response from incumbents and the complexity of telematics
integration across dozens of hardware vendors. **Overall recommendation: GO WITH
CONDITIONS** — viable if the founder can validate the ML prediction accuracy with a
pilot fleet before committing to full development.

---

## Feasibility Scorecard

| Dimension | Score (1-5) | Key Finding |
|---|---|---|
| Market Feasibility | 4 | Real pain point, $30B+ market, underserved SMB segment |
| Technical Feasibility | 3 | Core tech is proven; ML prediction accuracy is unvalidated |
| Financial Feasibility | 4 | Break-even at 180 customers; bootstrappable with runway |
| Legal Feasibility | 4 | No major regulatory blockers; standard SaaS compliance |
| Operational Feasibility | 3 | Solo founder — support load at scale is a concern |
| Schedule Feasibility | 3 | 6-month MVP is tight; 9 months more realistic |
| Pricing Viability | 4 | $99/mo fits market expectations; clear upgrade path |
| **Overall Score** | **3.6/5** | |

---

## Idea Profile

| Field | Value |
|---|---|
| Working product name | FleetPulse |
| One-sentence elevator pitch | Predictive maintenance scheduling for small fleet operators |
| Problem being solved | Small fleets lose $5K-$15K per vehicle/year to unplanned breakdowns |
| Who has this problem? | Fleet managers at companies with 10-200 vehicles |
| Proposed solution | SaaS dashboard that ingests telematics data and predicts failures |
| Product category | Web app (SaaS) |
| Deployment model | Cloud SaaS |
| Revenue intent | Bootstrapped, targeting sustainable profitability |
| Existing assets | Nothing yet — idea stage |
| Solo founder or team? | Solo founder (full-stack developer, 8 years experience) |
| Target launch timeframe | 6-9 months |
| Budget range | $10K-$50K (personal savings) |

**Assumptions made for this analysis:**
1. The founder is a full-stack developer comfortable with React, Node, and PostgreSQL — *assumed from stated experience*
2. Telematics hardware (OBD-II dongles) is already installed on target fleets — *assumed because this is standard in the segment*
3. The founder will work on this full-time — *assumed from 6-month timeline ambition*
4. The ML prediction component can achieve >80% accuracy — *NOT validated; flagged as key risk*
5. Target market is US-only at launch — *assumed for regulatory simplicity*

---

## Market & Commercial Feasibility

### Problem Validation

**Is this a real problem?** YES — strong signal.

- Reddit r/fleet and r/trucking: 50+ threads in the past year about unexpected breakdown costs
- ATRI (American Transportation Research Institute) 2025 report: vehicle maintenance is the
  #3 cost concern for fleet operators after fuel and driver wages
- Hacker News: 3 "Show HN" posts for fleet tools in 2025, all with 100+ comments
- Pain intensity: HIGH — a single roadside breakdown costs $500-$2,000 in towing + lost
  productivity, and fleets of 50 vehicles average 15-25 unplanned breakdowns per year

**Current solutions:**
- Spreadsheets and calendar reminders (most common for <50 vehicles)
- Fleetio ($5/vehicle/month, designed for 200+ vehicles — overkill for small operators)
- Samsara (enterprise, $30+/vehicle/month — priced out of reach)
- LubeLogger (open source, self-hosted — technically capable but no predictive features)

**Why haven't existing solutions solved it?**
Enterprise tools are overbuilt and overpriced for the SMB segment. Spreadsheets work but
don't predict failures. There's a clear gap for a purpose-built SMB tool with predictive
capabilities at the $99/month price point.

**Is the problem growing?** YES — last-mile delivery fleets are expanding rapidly (Amazon
DSPs, gig delivery, home services), creating new small fleet operators every month.

### Market Sizing

| Metric | Estimate | Methodology |
|---|---|---|
| TAM | $4.2B | 500K US fleets with 10-200 vehicles x $700/yr avg software spend |
| SAM | $840M | 100K fleets actively looking for digital maintenance solutions (20% of TAM) |
| SOM | $4.2M-$12.6M | 0.5%-1.5% of SAM in first 3 years = 3,500-10,500 customers |

SOM is well above the $100K/year viability threshold. Even the conservative scenario
($4.2M at 0.5% capture) supports a sustainable business.

### Competitive Landscape

| Competitor | Type | Price | Strengths | Weaknesses | Position |
|---|---|---|---|---|---|
| Fleetio | Direct | $5/vehicle/mo | Feature-rich, established | Complex, expensive for small fleets | Leader |
| Samsara | Direct | $30+/vehicle/mo | Hardware + software, enterprise | Way too expensive for SMB | Enterprise |
| Fleet Complete | Direct | Custom | GPS + maintenance | Legacy UX, complex onboarding | Challenger |
| LubeLogger | Indirect | Free (OSS) | Free, flexible | No predictive analytics, self-hosted | Niche |
| Spreadsheets | Indirect | $0 | Familiar, no learning curve | No automation, no predictions | Default |

**Market saturation**: Moderate — established players exist but SMB segment is underserved.
**Differentiation potential**: HIGH — predictive maintenance for SMB at an accessible price
is an unoccupied position.

### Customer Segments

**Persona 1: "Mike the Fleet Manager" (Primary)**
- Job: Manage maintenance schedules for 30-80 delivery vehicles
- Current solution: Excel spreadsheet + calendar reminders
- Pain: 1-2 surprise breakdowns per week costing $800-$1,500 each
- Pain intensity: 8/10
- Budget: Company card, $500/month tools budget
- WTP: $79-$149/month — would pay instantly if it demonstrably prevents breakdowns
- Perceived > objective value (breakdowns feel catastrophic in the moment)

**Persona 2: "Sarah the Owner-Operator" (Secondary)**
- Job: Run a 10-15 vehicle home services fleet (HVAC, plumbing, etc.)
- Current solution: Paper logbooks + mechanic relationship
- Pain: Vehicles down = technicians can't work = lost revenue
- Pain intensity: 7/10
- Budget: Personal business card, price-sensitive
- WTP: $49-$79/month
- Perceived < objective value (doesn't think of maintenance as a "software problem")

**Persona 3: "Dave the Amazon DSP Owner" (Growth)**
- Job: Manage 20-40 branded delivery vans for Amazon
- Current solution: Amazon provides basic tracking; maintenance is DIY
- Pain: Amazon penalizes DSPs for delivery failures due to vehicle issues
- Pain intensity: 9/10 (business survival at stake)
- Budget: Tight margins but will pay for survival tools
- WTP: $99-$199/month
- Perceived = objective value (directly tied to Amazon performance metrics)

**Persona 4: "Enterprise Procurement" (Future)**
- Job: Standardize maintenance tools across 200+ vehicles
- WTP: $500+/month or per-vehicle pricing
- Note: Not addressable at launch — requires SOC 2, SSO, SLA. Roadmap for Year 2.

### Brand Name Clearance

| Check | Findings | Risk Level |
|---|---|---|
| .com domain | fleetpulse.com — taken, redirects to a defunct logistics blog | MEDIUM |
| Other TLDs | fleetpulse.io — available; fleetpulse.app — available | LOW |
| Apple App Store | 0 exact matches | LOW |
| Google Play Store | 0 exact matches; 1 "Fleet Pulse GPS" (50 downloads, inactive) | LOW |
| USPTO trademarks | 0 live marks for "FleetPulse" in software classes | LOW |
| EUIPO trademarks | 0 live marks | LOW |
| Copyright records | No registered works | LOW |
| Web presence | 1 inactive blog at fleetpulse.com; no competing products | LOW |
| Sound-alikes | "Fleet Plus" (no software product found) | LOW |
| Look-alikes | "FleetPilot" — active fleet management company in UK | MEDIUM |

**Overall Assessment: GREEN** — Name is largely clear. The .com is held by an inactive
blog (potential acquisition for <$1K). FleetPilot in the UK is a different name and market.
Recommend securing fleetpulse.io immediately and pursuing .com acquisition.

---

## Technical Feasibility

### Requirements Analysis

| Requirement | Details | Complexity |
|---|---|---|
| Core functionality | Ingest telematics data, display maintenance timeline, predict failures | HIGH |
| Data storage | Time-series vehicle data, ~1GB/vehicle/year | MEDIUM |
| Integration requirements | OBD-II telematics APIs (Geotab, Samsara API, generic OBD) | HIGH |
| Performance | Dashboard loads <2s, predictions update daily | LOW |
| Security | Fleet data is business-sensitive; standard encryption | MEDIUM |
| Infrastructure | Cloud hosting, auto-scaling for batch ML jobs | MEDIUM |
| Platform | Web app (responsive), future mobile app | LOW |

### Recommended Stack

| Layer | Recommendation | Why | Alternatives |
|---|---|---|---|
| Frontend | Next.js (React) | SSR for dashboard perf, founder knows React | Svelte, Vue |
| Backend | Node.js + Express | Founder's primary language, fast iteration | Go, Python/FastAPI |
| Database | PostgreSQL + TimescaleDB | Relational + time-series for telematics data | InfluxDB, ClickHouse |
| ML Pipeline | Python (scikit-learn / XGBoost) | Proven for tabular prediction tasks | TensorFlow (overkill) |
| Infrastructure | AWS (ECS + RDS) | Mature, well-documented | GCP, Railway, Fly.io |
| Auth | Clerk | Fast to implement, SOC 2 compliant | Auth0, Supabase Auth |
| Payments | Stripe | Industry standard for SaaS billing | Paddle, LemonSqueezy |
| Monitoring | Datadog (free tier) | APM + logs in one place | Grafana + Loki |

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ML prediction accuracy below useful threshold | MEDIUM | HIGH | Validate with pilot fleet data before building full product |
| Telematics API fragmentation (too many hardware vendors) | HIGH | MEDIUM | Start with Geotab API only (largest market share), expand later |
| Time-series data volume exceeds cost expectations | LOW | MEDIUM | Aggregate raw data aggressively; keep only daily summaries after 90 days |
| Solo founder bottleneck on infra + ML + frontend | MEDIUM | MEDIUM | Use managed services everywhere; defer ML to post-MVP |

**No technical blockers identified.** All required technology exists and is proven.
The main uncertainty is ML prediction accuracy, which is testable before full commitment.

### Build vs. Buy

| Component | Build | Buy/Use | Recommendation | Rationale |
|---|---|---|---|---|
| Auth | Custom | Clerk | BUY | Save 2-3 weeks; SOC 2 compliant out of box |
| Payments/billing | Custom | Stripe Billing | BUY | Subscription management is solved |
| Telematics ingestion | Custom adapter | — | BUILD | No off-the-shelf solution for multi-vendor |
| ML predictions | Custom model | — | BUILD | Core differentiator; must own |
| Dashboard UI | Custom | — | BUILD | Core product experience |
| Email/notifications | Custom | Resend | BUY | Transactional email is a commodity |
| Hosting | — | AWS ECS | BUY | Don't manage servers |

### MVP Definition

**Must-have (launch blockers):**
- Connect to Geotab API and ingest vehicle telematics data
- Dashboard showing vehicle list, health status, upcoming maintenance
- Rule-based maintenance alerts (mileage-based, time-based)
- Basic reporting (maintenance history, cost tracking)
- Stripe billing integration

**Should-have (week 2-4):**
- ML-powered predictive alerts (v1 model)
- Email/SMS notifications for upcoming maintenance
- Multi-user access per account

**Nice-to-have (roadmap):**
- Mobile app
- Additional telematics provider integrations
- Parts ordering integration
- Enterprise features (SSO, audit log, API access)

**Explicitly out of scope for MVP:**
- Predictive ML (defer to v1.1 — launch with rule-based alerts first)
- Mobile app
- Enterprise tier
- Any telematics provider beyond Geotab

Estimated MVP scope: ~15 screens, ~30 API endpoints, ~15K-20K lines of code.

---

## Financial Feasibility

### Development Costs

**MVP:**

| Cost Category | Low Estimate | High Estimate | Assumptions |
|---|---|---|---|
| Development (labor) | $0 (founder) | $25,000 | Founder's time at $0 or 500 hrs x $50/hr opportunity cost |
| Design (UI/UX) | $500 | $3,000 | Tailwind templates + 1 freelance design review |
| Infrastructure (6 months) | $300 | $600 | AWS free tier + small RDS instance |
| Third-party services | $200 | $500 | Clerk, Resend, Stripe, Geotab dev account |
| Legal | $500 | $2,000 | LLC formation + template ToS/Privacy |
| Domain & branding | $100 | $1,200 | Domain + logo (Fiverr or AI-generated) |
| **Total MVP** | **$1,600** | **$32,300** |

**v1.0 (with ML predictions):**

| Cost Category | Low Estimate | High Estimate | Assumptions |
|---|---|---|---|
| Additional development | $0 (founder) | $15,000 | ML pipeline + additional integrations |
| QA & testing | $0 | $2,000 | Founder + beta tester feedback |
| Documentation | $0 | $500 | AI-assisted docs generation |
| Marketing launch | $1,000 | $5,000 | Content + targeted ads |
| **Total v1.0** | **$2,600** | **$54,800** |

### Operating Costs (Monthly)

| Cost | Month 1-3 | Month 4-6 | Month 7-12 | Year 2 |
|---|---|---|---|---|
| Hosting/infra | $50 | $100 | $200 | $500 |
| Third-party APIs | $50 | $100 | $150 | $300 |
| Support tools | $0 | $0 | $50 | $100 |
| Marketing | $200 | $500 | $1,000 | $2,000 |
| Legal/accounting | $50 | $50 | $100 | $200 |
| **Monthly Total** | **$350** | **$750** | **$1,500** | **$3,100** |

### Revenue Projections

| Scenario | Month 3 | Month 6 | Month 12 | Year 2 (monthly) |
|---|---|---|---|---|
| Conservative | $0 | $990 (10 customers) | $4,950 (50) | $14,850 (150) |
| Moderate | $495 (5) | $2,970 (30) | $11,880 (120) | $29,700 (300) |
| Optimistic | $990 (10) | $6,930 (70) | $24,750 (250) | $59,400 (600) |

Assumptions: $99/month ARPU, 5% monthly churn, moderate scenario assumes 15-20 new
customers/month after month 3.

### Break-Even Analysis

| Metric | Value |
|---|---|
| Monthly fixed costs | $1,500 (at steady state) |
| Revenue per customer (ARPU) | $99/mo |
| Variable cost per customer | $3/mo (hosting + API proportional) |
| Contribution margin | $96/mo |
| Customers needed to break even | 16 |
| Months to break even (moderate) | ~5 months after launch (~11 months total) |

### ROI Projections

| Metric | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Total investment | $35,000 | $35,000 | $35,000 |
| Cumulative revenue | $45,000 | $200,000 | $500,000 |
| Net position | +$10,000 | +$165,000 | +$465,000 |
| ROI % | 29% | 471% | 1,329% |

### Funding Assessment

**Can this be bootstrapped?** YES — with conditions.
- MVP cost is within founder's stated $10K-$50K budget
- Monthly burn is under $1,500 until revenue materializes
- Break-even at just 16 customers is highly achievable
- Founder needs 9-12 months of personal runway (living expenses)

This is a **lifestyle/indie business** opportunity, not venture-scale. $1M-$5M ARR
ceiling is realistic. This is a strength, not a weakness — it means the founder
retains full ownership and control.

---

## Legal & Regulatory Feasibility

### Business Structure & IP

| Question | Assessment |
|---|---|
| Recommended entity | LLC (single-member) — simple, liability protection, pass-through tax |
| IP protection | Trade secret for ML model weights; trademark for FleetPulse name |
| Open source considerations | Not applicable — proprietary SaaS |
| Terms of Service | Required — moderate complexity (data processing, SLA terms) |
| Privacy Policy | Required — collects vehicle location/operational data |

### Regulatory Compliance

| Regulation | Applies? | Impact | Compliance Cost | Timeline |
|---|---|---|---|---|
| GDPR | No (US-only at launch) | N/A | N/A | Future if expanding to EU |
| CCPA/CPRA | Yes (if CA customers) | LOW | $500 (privacy policy update) | Before launch |
| SOC 2 | Not yet | MEDIUM (enterprise sales) | $15K-$30K | Year 2 |
| FMCSA regulations | Aware but not directly applicable | LOW | $0 | Monitor |
| Data breach notification | Yes (state laws vary) | LOW | Built into incident response | Before launch |

### Legal Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Liability for incorrect maintenance predictions | MEDIUM | HIGH | Strong disclaimer in ToS; "advisory only" positioning |
| Telematics data privacy concerns | LOW | MEDIUM | Clear data handling policy; no PII collection |
| Trademark dispute (FleetPilot UK) | LOW | LOW | Different name, different market, different geography |

### Legal Budget

| Item | Estimated Cost | Priority |
|---|---|---|
| LLC formation | $200 | MUST — before accepting revenue |
| Terms of Service | $0-$500 (template + review) | MUST — before launch |
| Privacy Policy | $0-$300 (template + review) | MUST — before launch |
| Trademark filing (FleetPulse) | $350 | SHOULD — within 3 months of launch |
| **Total legal (Year 1)** | **$550-$1,350** | |

---

## Operational Feasibility

### Team Assessment

| Role | Needed? | Available? | Gap? | Solution |
|---|---|---|---|---|
| Lead developer | Yes | Yes (founder) | No | — |
| Designer | Part-time | No | Yes | Freelancer for initial design ($1-2K) |
| Marketing | Part-time | No | Yes | Founder handles initially; content + SEO |
| Customer support | Part-time | No | Yes | Founder handles; intercom/crisp for self-serve |
| DevOps | Minimal | Yes (founder) | No | Managed services reduce need |

### Scalability Concerns

| Users | Operational Impact | Action Required |
|---|---|---|
| 1-50 | Founder handles everything | Current plan |
| 50-200 | Support tickets become daily | Add self-serve docs + help center |
| 200-500 | Support + bug fixes consume 50%+ of time | Hire first support person or part-time dev |
| 500+ | Full-time dev needed; founder shifts to product/business | First full-time hire |

### Founder Capacity

- Full-time commitment: YES (stated)
- Financial runway: 12-18 months (stated $10K-$50K budget + savings)
- Burnout risk: MODERATE — solo founder building ML + full-stack + marketing
- Recommendation: defer ML to post-MVP to reduce scope and burnout risk

---

## Schedule Feasibility

### Project Timeline

| Phase | Duration | Milestone | Dependencies |
|---|---|---|---|
| Research & Planning | 2 weeks | PRD, tech decisions, Geotab API access | None |
| Design | 2 weeks | UI mockups, component library selected | PRD |
| MVP Development | 10 weeks | Core dashboard, rule-based alerts, billing | Design |
| Alpha Testing | 2 weeks | Internal testing, 2-3 friendly fleets | MVP |
| Beta / Early Access | 4 weeks | 10-20 beta users, feedback collected | Alpha |
| v1.0 Launch | 2 weeks | Public launch, marketing push | Beta |
| **Total to v1.0** | **~22 weeks (5.5 months)** | | |
| ML Predictions (v1.1) | 8 weeks | Predictive alerts live | v1.0 + pilot data |

### Critical Path

```
PRD (2w) → Design (2w) → MVP Dev (10w) → Alpha (2w) → Beta (4w) → Launch (2w) = 22 weeks
```

Parallelizable: Legal setup during dev (saves 0 weeks on critical path but reduces
post-launch risk). Marketing content creation during beta (saves 0 weeks but improves
launch readiness).

### Timeline Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Geotab API integration harder than expected | +2-4 weeks | MEDIUM | Start integration in week 1 as a spike |
| Scope creep (adding ML to MVP) | +4-8 weeks | HIGH | Strict MVP gate: no ML until v1.1 |
| Beta feedback requires major rework | +2-4 weeks | LOW | Alpha testing catches major issues first |

### Schedule Verdict

**TIGHT** — The 6-month target is achievable but requires disciplined execution. The
original 6-month timeline assumed ML in MVP, which is unrealistic. With ML deferred
to v1.1, the 5.5-month plan is feasible. Buffer of 2-4 weeks recommended.

**Realistic launch: 6-7 months from start.**

---

## Pricing & Go-to-Market Strategy

### Demand Curve Analysis

| Price Point | Likely Buyers | Est. Monthly Revenue (100 signups) |
|---|---|---|
| $0 (free forever) | All personas | $0 |
| $29/mo | Sarah + Mike + Dave | $29 x 70 = $2,030 |
| $49/mo | Sarah + Mike + Dave | $49 x 55 = $2,695 |
| $99/mo | Mike + Dave; Sarah uses free | $99 x 35 = $3,465 |
| $149/mo | Mike + Dave only | $149 x 20 = $2,980 |
| $299/mo | Dave only (enterprise) | $299 x 5 = $1,495 |

**Revenue-maximizing price band: $79-$99/month**

### Pricing Model: Freemium Subscription

**Rationale**: Fleet operators expect subscription pricing (matches Fleetio, Samsara).
A generous free tier for 1-3 vehicles captures Sarah-type small operators who may
grow. The $99 price point sits comfortably under the $1,000 procurement threshold,
enabling credit-card purchases without formal approval.

### Tier Structure

| Tier | Target Persona | Includes | Price |
|---|---|---|---|
| **Starter** | Sarah (small fleet) | Up to 5 vehicles, basic alerts, email support | **Free** |
| **Professional** | Mike (mid fleet) | Up to 50 vehicles, predictive alerts, priority support | **$99/mo** |
| **Business** | Dave (growing fleet) | Up to 200 vehicles, API access, phone support | **$249/mo** |
| **Enterprise** | Large fleets | Unlimited, SSO, SLA, dedicated CSM | **Contact us** |

Annual pricing: 2 months free (pay for 10).

### Launch Pricing Strategy

| Timeframe | Strategy | Price |
|---|---|---|
| Beta | Free for all beta users | $0 |
| Day 1 launch | Introduce paid tiers; beta users get 3 months free | $99/mo |
| Month 3 | Early adopter offer: lock in $79/mo for life (first 50 customers) | $79/mo |
| Month 6 | Introduce annual pricing at 2 months free | $99/mo or $990/yr |
| Month 12 | Launch Enterprise tier with first case study | Contact us |

### Marketing Strategy

**Channels (in priority order):**
1. Content marketing — blog posts on fleet maintenance cost reduction (SEO play)
2. Fleet management forums and communities (Reddit, fleet Facebook groups)
3. Geotab partner marketplace listing
4. Targeted Google Ads: "fleet maintenance software small business"
5. Conference presence at NAFA Fleet Management Association events

**Key messaging:**
1. "Predict breakdowns before they strand your driver" — speaks to Mike's pain
2. "Enterprise fleet intelligence at small business prices" — positions against Samsara
3. "5 minutes to set up, works with your existing telematics" — reduces switching cost fear

---

## Risk Analysis

### Consolidated Risk Register

| # | Risk | Source | Likelihood | Impact | Severity | Mitigation |
|---|---|---|---|---|---|---|
| 1 | ML prediction accuracy insufficient | Technical | MEDIUM | HIGH | HIGH | Validate with pilot data before building |
| 2 | Fleetio adds predictive features | Competitive | MEDIUM | HIGH | HIGH | Move fast; differentiate on simplicity + price |
| 3 | Telematics API fragmentation | Technical | HIGH | MEDIUM | HIGH | Start Geotab-only; add vendors based on demand |
| 4 | Solo founder burnout | Operational | MEDIUM | HIGH | HIGH | Defer ML; use managed services; strict scope |
| 5 | Incorrect prediction causes accident | Legal | LOW | HIGH | MEDIUM | "Advisory only" disclaimer; insurance |
| 6 | Slow customer acquisition | Market | MEDIUM | MEDIUM | MEDIUM | Free tier for awareness; content marketing |
| 7 | .com domain acquisition fails | Brand | LOW | LOW | LOW | Use fleetpulse.io as primary domain |

### SWOT Analysis

| | Helpful | Harmful |
|---|---|---|
| **Internal** | **Strengths**: Solo full-stack founder (fast iteration, low burn), clear target market, bootstrappable economics | **Weaknesses**: No ML expertise yet, no fleet industry connections, solo = single point of failure |
| **External** | **Opportunities**: Growing last-mile delivery market, telematics adoption accelerating in SMB, incumbents focused on enterprise | **Threats**: Fleetio downmarket expansion, new VC-funded entrant, Geotab building first-party maintenance features |

---

## Recommendation

### Verdict: GO WITH CONDITIONS

FleetPulse addresses a real, growing problem in an underserved market segment. The
economics work, the tech is buildable, and the legal landscape is clean. However,
the core value proposition — *predictive* maintenance — depends on ML accuracy that
is currently unvalidated.

### Conditions

1. **Validate ML feasibility first** (2-3 weeks): Obtain sample telematics data from
   a friendly fleet operator and build a proof-of-concept prediction model. If accuracy
   is below 70%, launch with rule-based alerts only and position as "smart scheduling"
   rather than "predictive maintenance."
2. **Secure fleetpulse.io domain** immediately (before any public branding)
3. **Defer ML to v1.1** — launch MVP with rule-based alerts to reduce timeline risk
4. **Line up 3-5 beta fleets** before starting development

### Recommended Next Steps

1. **This week**: Register fleetpulse.io, create Geotab developer account, reach out to
   3 fleet operators for pilot data
2. **Week 2-3**: Build ML proof-of-concept with sample data; assess prediction accuracy
3. **Week 4**: If ML validates, start full development. If not, pivot positioning to
   "smart maintenance scheduling" (still viable, lower ceiling)
4. **Month 1**: Form LLC, draft ToS/Privacy Policy from templates
5. **Month 2-4**: Build MVP (rule-based alerts, dashboard, billing)
6. **Month 5**: Alpha testing with pilot fleets
7. **Month 6-7**: Beta launch, collect feedback, iterate
8. **Month 7-8**: Public launch with early adopter pricing
9. **Month 9-10**: Add ML predictions as v1.1 (if validated)

---

## Davidson Pricing Checklist

- [x] Strategy: mid-market pricing ($99/mo) with free tier for awareness
- [x] Product definition: maintenance intelligence + peace of mind + cost savings
- [x] Fairness: priced at 1/3 of Fleetio on a per-fleet basis for the target segment
- [x] Customer profile: Mike (team budget, card), Sarah (personal, price-sensitive), Dave (business card)
- [x] Competitor reaction: Fleetio unlikely to drop to $99/mo; may add features
- [x] Sales model: self-serve web for Starter/Pro; inbound for Enterprise
- [x] Segmentation: Starter (free) / Professional / Business / Enterprise
- [x] Bundling: future opportunity with telematics hardware partners
- [x] First price set: $99/mo Professional tier
- [ ] Test and adjust: revisit at Month 3 based on conversion data

---

## Appendix: Assumptions & Methodology

**Data sources:**
- Market sizing: ATRI reports, IBISWorld fleet maintenance industry data, Geotab partner statistics
- Competitor pricing: publicly available pricing pages (accessed April 2026)
- Customer personas: based on fleet industry forums, user interviews cited in Fleetio blog posts
- Financial projections: estimated based on comparable SaaS companies in vertical markets

**Key assumptions that should be validated:**
1. ML prediction accuracy >70% is achievable with OBD-II telematics data alone
2. Geotab API provides sufficient data granularity for predictive maintenance
3. Fleet operators with 10-50 vehicles are willing to adopt SaaS tools (not just spreadsheets)
4. $99/month is within the self-serve purchase threshold for the target segment
5. Content marketing can generate 15-20 qualified leads per month by month 6
