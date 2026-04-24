---
name: testing-strategy
version: 1.0.0
description: Generates a right-sized, stack-aware testing strategy specifying what to unit test, integration test, E2E test, and manually test -- avoiding both under-testing and 100%-coverage dogma.
---

# testing-strategy

## When to use

- Starting a new project and need a testing plan.
- Reviewing whether your current testing approach still makes sense.
- Before a launch push to ensure critical paths have coverage.

## When NOT to use

- For generating actual test code (this produces the strategy doc, not tests).
- For running tests or checking coverage.

## Prerequisites

- Project must be onboarded in solo-dev-suite.

## Methodology

### Coverage targets are qualitative, not percentages

"High" means the high-risk modules are well covered. Not a number. Goodhart's law applies.

### Four categories

- **Unit** (30-50% effort): Pure business logic, math, validation, parsers. Skip UI glue.
- **Integration** (30-40% effort): The high-leverage tier. DB <-> API, auth flows, payment flows.
- **E2E** (10-20% effort): Only critical conversion paths. One flaky E2E test is worse than none.
- **Manual** (10-20% effort): Everything else. Documented so "manual" doesn't mean "skipped."

### Explicit skips matter

A strategy that says "don't bother testing UI components" is useful. Silence on UI components is ambiguous.

### Staleness detection

The `review_cadence` field (monthly/quarterly/biannual/annual) drives staleness warnings on `show`.

## Operations

### design

Create the initial testing strategy.

```
echo '{ full payload }' | python scripts/testing_tool.py design <slug> --from-stdin
```

### show

Display strategy with staleness check.

```
python scripts/testing_tool.py show <slug>
python scripts/testing_tool.py show <slug> --category unit
python scripts/testing_tool.py show <slug> --json
```

### iterate

Update the strategy (requires reason).

```
echo '{"reason":"Adding Stripe, need integration tests","categories":{"integration":{...}}}' \
  | python scripts/testing_tool.py iterate <slug> --from-stdin
```

### review

Mark strategy as reviewed, resets staleness timer.

```
python scripts/testing_tool.py review <slug>
```

### render

Generate TESTING_STRATEGY.md.

```
python scripts/testing_tool.py render <slug>
```

### delete

Remove sidecar.

```
python scripts/testing_tool.py delete <slug> --yes
```

## Files

| File | Purpose |
|------|---------|
| `scripts/testing_tool.py` | CLI with all subcommands |
| `templates/testing.schema.json` | Sidecar JSON Schema |
| `templates/TESTING_STRATEGY.md.tmpl` | Rendered doc template |
