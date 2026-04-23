---
name: tech-debt-register
description: Logs, categorizes, and prioritizes tech debt as it's incurred. Not a shame exercise -- a managed backlog with pay-down window recommendations and priority scoring.
---

# tech-debt-register

## When to use

- You've taken a shortcut and want to log it before you forget.
- You want to see what debt exists and decide what to pay down next.
- Pre-launch review: which debt items need resolution before shipping?
- Periodic debt review to update urgency windows and priorities.

## When NOT to use

- For auto-detecting code smells (this is human-logged, not a scanner).
- For tracking bugs (use an issue tracker).
- For feature requests (use mvp-scope-guardian).

## Prerequisites

- Project must be onboarded in solo-dev-suite (profile exists).
- No explicit init -- sidecar is created on first `log`.

## Methodology

### Categories

Every item is tagged with one or more: `design`, `code`, `infra`, `docs`, `dependencies`, `security`, `ui-ux`, `testing`, `performance`.

### Impact scoring

- **Impact**: low / medium / high / critical
- **Effort**: S / M / L / XL
- **Urgency window**: now / pre-launch / post-launch-30d / post-launch-90d / when-it-bites / never

### Priority score

```
priority = (impact_rank * urgency_rank) / effort_rank
```

Where impact: low=1, medium=2, high=4, critical=8; urgency: never=0, when-it-bites=1, post-launch-90d=2, post-launch-30d=3, pre-launch=4, now=5; effort: S=1, M=2, L=3, XL=4.

Higher score = pay down first. `list --recommend` sorts by this.

### Status lifecycle

- **open** -- logged and unresolved
- **paid-down** -- resolved with notes
- **accepted** -- won't-fix with required rationale

Reopening moves any status back to open.

## Operations

### log

Log a new debt item. Sidecar is auto-created on first log.

```
echo '{"title":"No tests on builder","description":"Shipped without coverage","categories":["testing"],"impact":"high","effort":"L","urgency_window":"post-launch-30d"}' \
  | python scripts/debt_tool.py log <slug> --from-stdin
```

Required: `title`, `description`. Defaults: impact=medium, effort=M, urgency=when-it-bites, categories=["code"].

### list

List items with optional filters and recommendation sorting.

```
python scripts/debt_tool.py list <slug>
python scripts/debt_tool.py list <slug> --recommend
python scripts/debt_tool.py list <slug> --status paid-down
python scripts/debt_tool.py list <slug> --category testing
```

### show

Show full details of a single item.

```
python scripts/debt_tool.py show <slug> --id TD01
```

### resolve

Mark as paid-down with resolution notes.

```
python scripts/debt_tool.py resolve <slug> --id TD01 --resolution-notes "Added unit tests"
```

### accept

Mark as won't-fix with required rationale.

```
python scripts/debt_tool.py accept <slug> --id TD01 --reason "Not worth the effort for this feature"
```

### reopen

Move resolved/accepted back to open.

```
python scripts/debt_tool.py reopen <slug> --id TD01
```

### render

Generate TECH_DEBT.md with summary, recommendations, open/resolved/accepted sections.

```
python scripts/debt_tool.py render <slug>
```

### delete

Remove the sidecar. No generated files to clean up.

```
python scripts/debt_tool.py delete <slug> --yes
```

## Files

| File | Purpose |
|------|---------|
| `scripts/debt_tool.py` | CLI with all subcommands |
| `templates/techdebt.schema.json` | Sidecar JSON Schema |
| `templates/TECH_DEBT.md.tmpl` | Rendered doc template |

## Testing

```bash
# 1. Log two items
echo '{"title":"No tests on workout builder","description":"Shipped without tests","categories":["testing"],"impact":"high","effort":"L","urgency_window":"post-launch-30d"}' \
  | python scripts/debt_tool.py log my-project --from-stdin

echo '{"title":"Stripe webhook not idempotent","description":"Duplicate deliveries cause duplicate charges","categories":["code","infra"],"impact":"critical","effort":"S","urgency_window":"pre-launch"}' \
  | python scripts/debt_tool.py log my-project --from-stdin

# 2. List + recommend (TD02 should rank first: critical/S/pre-launch)
python scripts/debt_tool.py list my-project --recommend

# 3. Resolve TD02
python scripts/debt_tool.py resolve my-project --id TD02 --resolution-notes "Added event_id tracking"

# 4. List open only (should show TD01 only)
python scripts/debt_tool.py list my-project --status open

# 5. Render
python scripts/debt_tool.py render my-project

# 6. Delete
python scripts/debt_tool.py delete my-project --yes
```
