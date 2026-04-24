# Contributing to Solo Dev Suite

Thanks for your interest in contributing! The suite is designed to be extended with new skills covering any part of the solo developer lifecycle.

## Types of Contributions

### New Child Skills

The highest-impact contribution. Each skill is self-contained and follows a consistent structure.

### Bug Fixes

Found a broken script or incorrect schema? PRs welcome.

### Documentation

Improvements to SKILL.md files, README, or this guide.

## Skill Structure Requirements

Every skill must include:

```
skills/<skill-name>/
  SKILL.md                        # Frontmatter (name, version, description) + full playbook
  .claude-plugin/
    plugin.json                   # Plugin metadata (name, version, author, license, keywords)
  scripts/
    <tool>.py                     # Pure Python 3.9+ stdlib, no pip dependencies
  templates/
    <schema>.schema.json          # JSON Schema for any sidecar data (optional)
```

### SKILL.md Frontmatter

```yaml
---
name: my-new-skill
version: 1.0.0
description: One-line description of what this skill does and when it triggers.
---
```

### Script Conventions

All scripts must follow these patterns (see `profile_io.py` as the reference implementation):

- **Pure stdlib** -- no external dependencies. `import json`, not `import requests`.
- **UTF-8 stdout wrapper** -- `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')`
- **`_err()` helper** -- all diagnostics to stderr, prefixed with `[script_name]`
- **`argparse` with subparsers** -- each command sets `func=cmd_*` via `set_defaults`
- **`main(argv=None)`** -- accepts optional argv for testability
- **Atomic writes** -- write to `.tmp` then `.replace()`, never write directly
- **Documented exit codes** -- 0=success, non-zero=specific failure

### Plugin Registration

1. Create `.claude-plugin/plugin.json` in your skill directory
2. Add an entry to the root `.claude-plugin/marketplace.json`
3. Add an entry to `skills/solo-dev-suite/data/children.json` with:
   - `name`, `version`, `status`, `phases`, `depends_on`, `enhances`
   - `description`, `triggers`, `output_location`

### Profile Integration

If your skill reads or writes profile data:

- **Read** via `profile_io.py show <slug> --json`
- **Write** via `echo '<patch>' | profile_io.py update <slug> --from-stdin`
- Sidecar files go in `profiles/<slug>.<skill-name>.json`
- Keep profile mirrors lean -- full data in the sidecar, summary in the profile

## Quality Checklist

Before submitting:

- [ ] `python -c "import py_compile; py_compile.compile('scripts/<tool>.py', doraise=True)"` passes
- [ ] Script runs with `--help` without errors
- [ ] SKILL.md has "When to use" and "When NOT to use" sections
- [ ] No external pip dependencies
- [ ] No hardcoded absolute paths (use `Path(__file__).resolve().parent`)
- [ ] Tested on at least one real project profile
- [ ] Entry added to `children.json` with correct phases and dependencies

## Submitting

1. Fork the repo
2. Create a branch: `git checkout -b skill/<skill-name>`
3. Add your skill following the structure above
4. Test: create a throwaway profile, run your skill, verify output
5. Open a PR with:
   - What the skill does
   - Which lifecycle phase(s) it covers
   - Example output

## Code of Conduct

Be constructive. This is a tool for solo developers who are already stretched thin -- contributions should reduce complexity, not add it.

## Questions?

Open an issue with the `question` label.
