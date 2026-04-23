---
name: adr-generator
description: Generates and maintains Architecture Decision Records (ADRs) in the Michael Nygard format -- numbered, sequentially stored Markdown docs capturing context, options considered, decision, and consequences. Triggers on "generate an ADR", "record this decision", "log architecture decision", "why did I choose X", "add an ADR", or "list my ADRs". Part of the solo-dev-suite -- loads the project profile via the orchestrator. Not for runtime config changes (those are just code) or meeting notes (use a wiki).
---

# ADR Generator

Generates and maintains Architecture Decision Records -- one-per-decision Markdown docs answering the question your future self will ask: "Why the hell did I do it this way?"

Uses the Michael Nygard format (industry standard). Each ADR lives as a numbered file in `<repo>/docs/adr/`. The sidecar tracks metadata only; the Markdown files are the source of truth.

## When to use this skill

- **Recording a tech choice** -- you just picked SQLite over Postgres, Next.js over Remix, Stripe over LemonSqueezy. Write it down before the reasoning evaporates.
- **During architecture phase** -- catalog the foundational decisions that shape the entire project.
- **Mid-build pivots** -- you're changing a previous decision. Supersede the old ADR so there's a paper trail.
- **Pre-launch documentation** -- used alongside auto-docs to ensure every "why" is captured before you forget.

## When NOT to use this skill

- **No profile exists** -- run the orchestrator first.
- **Runtime configuration** -- changing a feature flag or env var isn't an architecture decision.
- **Bug fixes** -- fixing a bug isn't a decision. If the fix involves a significant design change, that's an ADR.
- **Third-party service tracking** -- use integration-mapper for that. ADRs record *why* you chose a service, not its risk profile.

## Prerequisites

- Project profile must exist: `solo-dev-suite/profiles/<slug>.json`
- Sidecar lives at: `solo-dev-suite/profiles/<slug>.adr.json` (created on first `new`)
- ADR files written to: `<repo>/docs/adr/NNNN-<slug>.md`

## Methodology -- The Michael Nygard Format

Every ADR answers five questions:

1. **Title** -- Short, decision-framed. "Use SQLite instead of Postgres for v1", not "Database discussion".
2. **Status** -- proposed / accepted / superseded / deprecated. Lifecycle is forward-only.
3. **Context** -- What's the forcing function? What constraints or requirements drove this decision?
4. **Decision** -- What we're doing, in active voice. "We will use SQLite." Not "It was decided that..."
5. **Consequences** -- Good, bad, and neutral outcomes. Be honest about tradeoffs.

Plus two optional but encouraged sections:
- **Alternatives Considered** -- What else was on the table and why it lost.
- **Notes** -- Links, benchmarks, trade-off math, Slack threads, anything supporting the decision.

### Status transitions

Allowed transitions:
- `proposed` -> `accepted` (decision confirmed)
- `accepted` -> `deprecated` (no longer applies, but not replaced)
- `accepted` -> `superseded` (replaced by a newer ADR)

Rejected transitions: anything going backwards (deprecated -> accepted) or skipping states.

### Numbering

Sequential, zero-padded to 4 digits: `0001`, `0002`, etc. Numbers are never recycled. If ADR 3 is superseded, the next new ADR is still whatever comes after the current max.

### Supersession

When ADR N supersedes ADR M:
- ADR M gets `superseded_by: N` and status changes to `superseded`
- ADR N gets `supersedes: M`
- Both Markdown files are re-rendered with updated status headers

## Operations

### 1. New (create ADR)

**Goal**: Record a new architecture decision.

**Workflow**:

1. User describes the decision (or Claude drafts from conversation context).
2. Populate the five Nygard sections + alternatives + tags.
3. Persist:
   ```bash
   echo '<payload>' | python scripts/adr_tool.py new <slug> --from-stdin
   ```

**Stdin shape**:
```json
{
  "title": "Use SQLite instead of Postgres for v1",
  "status": "accepted",
  "context": "Solo dev, no traffic yet, want zero-ops database.",
  "decision": "Ship with SQLite embedded. Migrate to Postgres if/when traffic justifies it.",
  "consequences": {
    "positive": ["Zero ops overhead", "No separate DB process"],
    "negative": ["Migration pain later if we outgrow it"],
    "neutral": ["SQLAlchemy abstracts most SQL differences"]
  },
  "alternatives": [
    {"name": "Postgres", "description": "Industry standard relational DB", "why_rejected": "Overkill for a solo dev with zero users"}
  ],
  "tags": ["database", "infrastructure"],
  "notes": ""
}
```

The tool auto-assigns the next number, derives a slug from the title, writes the Markdown file, updates the sidecar, and mirrors to the profile.

### 2. Show (view single ADR)

```bash
python scripts/adr_tool.py show <slug> --number <N>
python scripts/adr_tool.py show <slug> --number <N> --json
```

Human-readable output shows all sections. `--json` returns the sidecar entry.

### 3. List (all ADRs)

```bash
python scripts/adr_tool.py list <slug>
python scripts/adr_tool.py list <slug> --status accepted
python scripts/adr_tool.py list <slug> --tag database
python scripts/adr_tool.py list <slug> --json
```

Shows numbered list with status indicators. Filters by status or tag.

### 4. Supersede (replace an ADR)

```bash
python scripts/adr_tool.py supersede <slug> --old-number <N> --new-number <M>
```

Marks ADR N as superseded by ADR M. Updates both sidecar entries and re-renders both Markdown files.

### 5. Status (change ADR status)

```bash
python scripts/adr_tool.py status <slug> --number <N> --to <status>
```

Changes status with transition validation. Only allowed transitions succeed.

### 6. Render (regenerate all files)

```bash
python scripts/adr_tool.py render <slug> [--output-dir <path>]
```

Re-renders all ADR Markdown files plus `index.md`. Idempotent -- running twice produces identical output.

### 7. Delete (remove sidecar)

```bash
python scripts/adr_tool.py delete <slug> [--yes]
```

Removes the sidecar file. Does NOT delete the ADR Markdown files -- those are historical record and belong to the repo.

## Sidecar data shape

Authoritative schema: `templates/adr.schema.json`. Top-level keys:

- `schema_version` (const 1)
- `project_slug` (kebab-case)
- `created_at` / `updated_at` (ISO timestamps)
- `adrs[]` -- metadata entries
  - `number`, `slug`, `title`, `status`, `created_at`
  - `superseded_by` (number or null), `supersedes` (number or null)
  - `tags` (string array)
  - `context`, `decision`, `consequences` (positive/negative/neutral arrays)
  - `alternatives[]` (name/description/why_rejected)
  - `notes`

## Profile mirror

After every sidecar write, `profile.adr_model` is updated:
```json
{
  "total_adrs": 7,
  "accepted": 5,
  "proposed": 1,
  "superseded": 1,
  "latest_number": 7,
  "latest_title": "Switch client state management to Zustand"
}
```

Also updates `last_skill_run["adr-generator"]`.

## Output docs

- `<repo>/docs/adr/NNNN-<slug>.md` -- one per ADR
- `<repo>/docs/adr/index.md` -- table of all ADRs grouped by status

## Files

```
adr-generator/
├── SKILL.md                          # this file
├── scripts/
│   └── adr_tool.py                   # new / show / list / supersede / status / render / delete
└── templates/
    └── adr.schema.json               # JSON Schema for sidecar
```

## Testing

```bash
echo '{"title":"Use SQLite for v1","status":"accepted","context":"Solo dev, no traffic yet.","decision":"Ship with SQLite.","consequences":{"positive":["Zero ops"],"negative":["Migration later"],"neutral":[]},"alternatives":[{"name":"Postgres","description":"x","why_rejected":"Overkill"}],"tags":["database"]}' \
  | python scripts/adr_tool.py new my-project --from-stdin

echo '{"title":"Choose React over Vue","status":"accepted","context":"Need component library.","decision":"Use React.","consequences":{"positive":["Ecosystem"],"negative":["Complexity"],"neutral":[]},"alternatives":[{"name":"Vue","description":"x","why_rejected":"Smaller ecosystem"}],"tags":["frontend"]}' \
  | python scripts/adr_tool.py new my-project --from-stdin

python scripts/adr_tool.py list my-project
python scripts/adr_tool.py list my-project --status accepted
python scripts/adr_tool.py show my-project --number 1
python scripts/adr_tool.py supersede my-project --old-number 1 --new-number 2
python scripts/adr_tool.py status my-project --number 2 --to deprecated
python scripts/adr_tool.py render my-project
python scripts/adr_tool.py delete my-project --yes
```

Expected: new creates sidecar + ADR .md files + mirrors to profile, list shows status indicators and filters work, supersede updates both entries bidirectionally, status validates transitions, render produces index.md, delete removes sidecar but .md files survive.
