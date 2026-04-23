# Market Feasibility — Claude Code Plugin

A Claude Code plugin that takes a software product idea and produces a comprehensive Market Feasibility Report covering seven dimensions of viability plus pricing and go-to-market strategy.

## Install

```bash
claude plugin add https://github.com/your-username/solo-dev-suite
```

## What It Does

Given a product idea (described in plain text, a pitch document, or conversational description), this plugin produces a full feasibility study covering:

- **Market & Commercial Feasibility** — problem validation, TAM/SAM/SOM, competitive landscape, customer personas, brand name clearance
- **Technical Feasibility** — requirements analysis, recommended tech stack, build vs. buy, MVP definition
- **Financial Feasibility** — development costs, operating costs, revenue projections, break-even analysis, ROI
- **Legal & Regulatory Feasibility** — business structure, IP, compliance, legal risks
- **Operational Feasibility** — team assessment, scalability plan, founder capacity
- **Schedule Feasibility** — timeline, critical path, risk factors
- **Pricing & Go-to-Market** — demand curve, pricing model, tier structure, launch strategy, marketing

The report concludes with a **GO / GO WITH CONDITIONS / PIVOT RECOMMENDED / NO-GO** verdict.

## How to Invoke

Describe your software product idea and ask for a feasibility assessment:

```
I want to build an app that helps small fleet operators predict vehicle maintenance
needs using telematics data. Is this viable? Run a feasibility study.
```

Or point to existing documents:

```
Here's my pitch deck at ~/docs/pitch.pdf — run a feasibility study on this idea.
```

## License

MIT
