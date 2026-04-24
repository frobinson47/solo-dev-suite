---
name: design-loop
version: 1.0.0
description: Generates a customized design-exploration loop prompt for an existing project by discovering its stack, domain, and aesthetic, then tailoring references and constraints accordingly. Triggers on requests like "design loop on {project}", "refine the UI of this project", "explore design directions for {project}", "make this look more polished", "visual refresh", "modernize the UI", or "UI audit". Not for greenfield design, CSS debugging, or single-component tweaks — requires a target directory with an existing UI surface to analyze.
---

# Design Loop

Turns a project directory into a customized, multi-loop design exploration prompt. Does **not** execute the loop — produces the prompt that a separate loop runner consumes.

## When to use

- User points at an existing codebase and asks to improve, refine, or polish the UI
- User wants a structured design exploration, not a single mockup
- User mentions "design loop", "explore directions", "modernize", "visual refresh", "UI audit"

## When NOT to use

- **Greenfield design with no existing code** — use the `brainstorming` skill. This skill exits early if `discover.py` finds no UI surface.
- **Single-component tweaks** ("change this button color") — just make the change.
- **CSS debugging or pixel-perfect bug fixes** — those are surgical, not exploratory.
- **Pure backend projects with no UI** — exit early and say so.

## Workflow

### 1. Confirm the target path

If the user didn't supply one, ask. If the path doesn't exist or isn't a directory, stop and surface that before running anything else.

### 2. Run discovery

```bash
mkdir -p <target_path>/design-exploration
python "<SKILL_DIR>/scripts/discover.py" <target_path> \
  > <target_path>/design-exploration/context.json
```

Handle two early-exit cases based on what `discover.py` emits:

- **No UI surface detected** (no component dirs, no style files, no UI framework, `project_type == "unknown"` with zero domain hits): stop. Tell the user this looks greenfield or backend-only and suggest the `brainstorming` skill. Do not generate a prompt.
- **Multiple UI surfaces detected** (monorepo with e.g. `apps/admin` + `apps/marketing`): `discover.py` emits a `ui_surfaces` array. Ask the user which surface to target, then re-run with `--surface apps/admin` passed to `generate_prompt.py`.

### 3. Surface discovery decisions

Before generating the prompt, print these fields from `context.json` so the user can override:

- `project_type`
- `ui_framework`
- `style_system`
- First 5 references that would be auto-picked for this `project_type`
- `component_dirs` and any existing screenshots/mockups
- `data_version` of the references/dimensions libraries

Ask: "Override any of these with `--type`, `--refs`, `--surface`, `--hero`, or `--runner`?"

### 4. Generate the prompt

```bash
python "<SKILL_DIR>/scripts/generate_prompt.py" \
  <target_path>/design-exploration/context.json \
  > <target_path>/design-exploration/LOOP_PROMPT.md
```

### 5. Validate the output contract

```bash
python "<SKILL_DIR>/scripts/validate_prompt.py" \
  <target_path>/design-exploration/LOOP_PROMPT.md
```

If validation fails, the template or generator regressed — fix before handing off. Do not ship a prompt that doesn't pass validation.

### 6. Hand off

Print the full path to `LOOP_PROMPT.md` and the runner invocation. The default is `/loop`, but any exploration runner works — the prompt itself is runner-agnostic.

```
Prompt ready: <target_path>/design-exploration/LOOP_PROMPT.md
Suggested invocation: /loop 10m  (6 loops)
```

If the user passed `--runner` to `generate_prompt.py`, echo that invocation instead.

## Overriding discovery

Pass hints through `generate_prompt.py` to skip or correct discovery:

| Flag | Purpose | Default |
|------|---------|---------|
| `--type` | `saas-dashboard \| marketing \| dev-tool \| internal-ops \| ecommerce \| creative \| game \| docs` | auto-detected |
| `--refs` | Comma-separated reference override, e.g. `linear,vercel,stripe` | auto-picked from library |
| `--surface` | UI surface path in a monorepo, e.g. `apps/admin` | first detected |
| `--loops` | Loop count | `6` |
| `--duration` | Per-loop duration | `10m` |
| `--hero` | Final hero mockup target | type-appropriate default |
| `--runner` | Runner invocation embedded in handoff | `/loop` |
| `--min-viewport` | Minimum viewport spec | `1280x800` |

Example:

```bash
python generate_prompt.py context.json \
  --type creative --refs figma,ableton,arc --loops 8 --runner /loop
```

## Output contract

Every generated prompt MUST include the items below, and `validate_prompt.py` asserts each one. If you add a required section, update the validator in the same commit.

1. Mission statement naming the project and its detected type
2. Reference set (5 products, studied not copied)
3. Per-loop deliverables requirement (minimum one of five artifact types)
4. Exploration dimensions scoped to the project type
5. Detected stack constraints (framework, style system, component dirs)
6. Loop-N convergence clause producing `manifesto.md` + hero mockup
7. Data library version tag (so stale prompts are spottable later)

## Files

```
design-loop/
├── SKILL.md
├── scripts/
│   ├── discover.py           # scans target, emits context.json
│   ├── generate_prompt.py    # fills template from context
│   └── validate_prompt.py    # asserts output contract
├── templates/
│   └── loop-prompt.md.tmpl   # parameterized exploration prompt
├── data/
│   ├── references.json       # project-type → reference products (versioned)
│   ├── dimensions.json       # project-type → exploration dimensions (versioned)
│   └── README.md             # schema + allowed project types
├── fixtures/
│   ├── nextjs-dashboard/     # sample + expected outputs
│   ├── streamlit-app/
│   └── static-site/
└── tests/
    └── test_pipeline.py      # end-to-end fixture diff test
```

## Tuning

The reference and dimensions libraries are the highest-leverage places to improve output quality. When a generated prompt produces weak design directions, first check whether the references and dimensions matched the project. Edit `data/references.json` and `data/dimensions.json` rather than rewriting the template.

Both data files carry a `"version"` field (e.g. `"2026.04"`). Bump it on non-trivial edits. `generate_prompt.py` writes the version into the prompt header and warns when a `context.json` was produced against an older library version than the current one.

See `data/README.md` for the full schema, allowed `project_type` values, and field definitions — edit that doc if you extend the libraries.

## Testing

Run `pytest tests/` after any change to `discover.py`, `generate_prompt.py`, the template, or the data files. Fixtures under `fixtures/` are synthetic project skeletons with pinned expected outputs; the test diffs the generated `context.json` and `LOOP_PROMPT.md` against the expected files and fails loud on drift.

When a fixture's expected output changes legitimately (e.g. you bumped the references library), regenerate and commit the updated expected files in the same PR.
