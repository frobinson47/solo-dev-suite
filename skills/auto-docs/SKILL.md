---
name: auto-docs
version: 1.0.0
description: Generates and maintains project documentation (README, SETUP, ARCHITECTURE, CHANGELOG) by pulling from the profile and sibling sidecars. Re-runnable at every milestone so docs stay current without being a full-time job.
---

# auto-docs

## When to use

- The project needs baseline documentation and you don't want to write it from scratch.
- You've reached a milestone and docs need refreshing.
- You're adding a release and need the changelog updated.
- You want architecture docs that automatically reflect ADRs, integrations, and stack info.

## When NOT to use

- For API reference docs (use Sphinx, TypeDoc, etc.).
- For user-facing product docs or marketing copy.
- For docs that don't map to the four generated files (README, SETUP, ARCHITECTURE, CHANGELOG).

## Prerequisites

- Project must be onboarded in solo-dev-suite (profile exists).
- Run `init` once with user_content (headline, status badge, install steps).
- Other sidecars (scope, pricing, ADR, integrations, security) are optional -- auto-docs pulls from them when they exist and omits sections cleanly when they don't.

## Methodology

### What gets generated

1. **README.md** -- The front door. Project name, headline, status, stack summary, description, target users. Conditionally includes pricing teaser, latest release, screenshots, contact info.
2. **SETUP.md** -- Dev environment setup. Stack from profile, user-supplied install steps, hosting info.
3. **ARCHITECTURE.md** -- Tech stack table, third-party services (from integration-mapper), ADR summary (from adr-generator), hosting details.
4. **CHANGELOG.md** -- Versioned release notes, newest first. Breaking changes, highlights, fixes.

### Source pulling

Each doc conditionally pulls from the profile and sibling sidecars. If a sidecar doesn't exist, that section is simply omitted -- no errors, no placeholder text.

### Preserved regions

Users can add custom prose between `<!-- auto-docs:preserved:start -->` and `<!-- auto-docs:preserved:end -->` markers. These regions survive regeneration. Each template includes one preserved region by default.

### Safety

- `generate` checks if an existing file has auto-docs markers before overwriting. If a hand-crafted file exists without markers, it refuses unless `--force` is passed.
- Releases are append-only. No editing past releases.
- `delete` removes the sidecar but preserves all generated .md files.

## Operations

### init

Create the docs sidecar with user-supplied content.

```
echo '{"headline":"...","status_badge":"in-development","install_steps":["Clone","Install","Run"],"support_contact":"hi@example.com"}' \
  | python scripts/docs_tool.py init <slug> --from-stdin
```

Required fields: `headline`, `status_badge`, `install_steps`, `support_contact`.
Optional: `screenshots` (array of `{path, caption}`).

Valid status badges: `in-development`, `alpha`, `beta`, `production`, `maintenance`.

### generate

Regenerate one or all doc files from current profile + sidecar state.

```
python scripts/docs_tool.py generate <slug>
python scripts/docs_tool.py generate <slug> --only README
python scripts/docs_tool.py generate <slug> --force
```

### release

Append a new release entry. Regenerate CHANGELOG + README afterward.

```
echo '{"version":"0.1.0","headline":"Initial beta","highlights":["auth","workouts"],"fixes":[],"breaking":[]}' \
  | python scripts/docs_tool.py release <slug> --from-stdin
```

### update-content

Modify user_content fields (partial merge).

```
echo '{"headline":"New headline","status_badge":"beta"}' \
  | python scripts/docs_tool.py update-content <slug> --from-stdin
```

### show

Display sidecar state.

```
python scripts/docs_tool.py show <slug>
python scripts/docs_tool.py show <slug> --json
```

### delete

Remove the docs sidecar. Generated .md files are preserved.

```
python scripts/docs_tool.py delete <slug> --yes
```

## Files

| File | Purpose |
|------|---------|
| `scripts/docs_tool.py` | CLI with all subcommands |
| `templates/docs.schema.json` | Sidecar JSON Schema |
| `templates/README.md.tmpl` | README template |
| `templates/SETUP.md.tmpl` | SETUP template |
| `templates/ARCHITECTURE.md.tmpl` | ARCHITECTURE template |
| `templates/CHANGELOG.md.tmpl` | CHANGELOG template |

## Testing

Run against a real profile (my-project):

```bash
# 1. Init
echo '{"headline":"Client portal for trainers","status_badge":"in-development","install_steps":["Clone the repo","Copy .env.example to .env","Run npm install","Run docker-compose up -d","Run npm run dev"],"support_contact":"hi@my-project.com"}' \
  | python scripts/docs_tool.py init my-project --from-stdin

# 2. Generate all docs
python scripts/docs_tool.py generate my-project --force

# 3. Show
python scripts/docs_tool.py show my-project

# 4. Release
echo '{"version":"0.1.0","headline":"Initial beta","highlights":["Trainer auth","Client invite flow"],"fixes":[],"breaking":[]}' \
  | python scripts/docs_tool.py release my-project --from-stdin

# 5. Regenerate (changelog should have release)
python scripts/docs_tool.py generate my-project

# 6. Verify preserved regions survive
# 7. Delete
python scripts/docs_tool.py delete my-project --yes
```
