# Market Feasibility Report Skill — Usage Guide

## How to Install

Copy the `market-feasibility-report/` folder into your Claude Code skills directory:

```bash
# Typical location (adjust to your setup)
cp -r market-feasibility-report/ ~/.claude/skills/

# Or if you use a project-level CLAUDE.md:
cp -r market-feasibility-report/ /your/project/.claude/skills/
```

---

## How to Invoke

In any Claude Code session, describe your software product idea and ask for a feasibility
assessment. Examples:

```
I want to build an app that helps small fleet operators predict vehicle maintenance
needs using telematics data. Is this viable? Run a feasibility study.

Feasibility report for a SaaS tool that automates compliance monitoring for
small healthcare clinics.

I have an idea for a CLI tool that generates API documentation from OpenAPI specs
with AI-powered examples. Should I build this?

Run a market feasibility study on this concept: a marketplace connecting freelance
drone pilots with commercial property inspection companies.
```

You can also provide supporting documents:

```
Here's my pitch deck at ~/docs/pitch.pdf — run a feasibility study on this idea.

I have some notes about my project idea at ./project-notes.md — assess its viability.

Check out my early prototype at https://github.com/user/prototype and tell me
if this is worth building into a full product.
```

---

## What the Report Covers

The Market Feasibility Report assesses your idea across **seven dimensions**:

### Core Feasibility Analysis
- **Market feasibility** — problem validation, TAM/SAM/SOM market sizing, competitive
  landscape, customer personas
- **Technical feasibility** — requirements analysis, recommended tech stack, build vs. buy
  decisions, MVP definition, technical risks
- **Financial feasibility** — development costs, operating costs, revenue projections,
  break-even analysis, ROI, funding assessment
- **Legal & regulatory feasibility** — business structure, IP protection, regulatory
  compliance, legal risks and costs
- **Operational feasibility** — team assessment, operational requirements, scalability
  plan, founder capacity evaluation
- **Schedule feasibility** — project timeline, critical path analysis, timeline risks,
  schedule verdict

### Pricing & Go-to-Market (inherited from software-valuation)
- **Brand name clearance** — domain, trademark, app store, web presence checks
- **Demand curve analysis** — revenue-maximizing price band
- **Pricing model recommendation** — subscription, freemium, one-time, usage-based, etc.
- **Tier/versioning structure** — Free / Starter / Pro / Enterprise
- **Launch pricing strategy** — Day 1 through Month 12 pricing evolution
- **Marketing strategy** — channels, messaging, reference point management

### Risk & Recommendation
- **Consolidated risk register** — all risks ranked by severity
- **SWOT analysis** — strengths, weaknesses, opportunities, threats
- **Feasibility scorecard** — 1-5 score across all seven dimensions
- **Go/No-Go verdict** — GO, GO WITH CONDITIONS, PIVOT RECOMMENDED, or NO-GO
- **Concrete next steps** — time-bound action items

---

## Input Tips

### The More Context, the Better
The skill works with as little as a single sentence ("I want to build X"), but richer
input produces a much better report. Consider providing:
- Who has the problem and how painful it is
- How people solve the problem today
- Your background and available resources (solo founder? team? budget?)
- Your timeline expectations
- Any competitors you already know about

### Supporting Documents
You can attach or point to:
- Pitch decks (PDF, PPTX)
- Business plans or PRDs
- Market research notes
- Early prototypes or repos
- Competitor analysis you've already done

### What If the Idea Is Vague?
That's fine — the skill will ask clarifying questions (batched into a single round of
5-7 questions max) before proceeding. A vague idea just means more assumptions in the
report, which are clearly labeled so you can refine them.

---

## Optional: Add to CLAUDE.md

If you want this skill always available in a specific project, add to your `CLAUDE.md`:

```markdown
## Skills

### Market Feasibility Report
When asked to assess an idea's viability, run a feasibility study, or evaluate whether
something is worth building, use the skill at
`.claude/skills/market-feasibility-report/SKILL.md`.
The feasibility theory reference is at
`.claude/skills/market-feasibility-report/feasibility-theory.md`.
An example output is at
`.claude/skills/market-feasibility-report/example-output-report.md`.
```

---

## Relationship to Software Valuation Plugin

This skill is a fork of the **software-valuation** plugin (software-pricing-strategy skill).
Key differences:

| | Software Valuation | Market Feasibility |
|---|---|---|
| **Input** | Existing codebase (local path or GitHub URL) | Product idea (text, doc, or early prototype) |
| **Primary question** | "What should I charge for this?" | "Should I build this at all?" |
| **Output** | Pricing & marketing strategy report | Full feasibility study + pricing strategy |
| **Scope** | Pricing, versioning, market positioning | Technical, financial, legal, operational, schedule, market, pricing |
| **Best for** | Products ready to monetize | Ideas at the pre-build stage |

The two skills are complementary: use **Market Feasibility** when evaluating whether to
start a project, then use **Software Valuation** once the product is built and ready
to price.

---

## Theoretical Basis

This skill combines two bodies of knowledge:

**Feasibility Study Methodology:**
- Seven-dimension viability assessment
- TAM/SAM/SOM market sizing (bottom-up and top-down)
- SWOT analysis
- Critical path analysis
- Break-even and ROI modeling
- Risk scoring matrices

**Pricing Theory (Neil Davidson's *Don't Just Roll the Dice*):**
- Demand curve economics
- Perceived vs. objective value
- Reference point psychology
- Versioning and price discrimination
- Bundling math
- Network effects and tipping points
- Switching cost mitigation
- Price as brand signal
- Purchasing threshold awareness
