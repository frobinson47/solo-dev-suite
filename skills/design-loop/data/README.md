# Data Library Schema

Both `references.json` and `dimensions.json` share the same envelope:

```json
{
  "version": "YYYY.MM",
  "_comment": "optional note to future editors",
  "project_types": {
    "<project_type>": [...]
  }
}
```

## Fields

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `version` | string, `YYYY.MM` format | yes | Bumped on non-trivial edits. Written into every generated prompt's header. `generate_prompt.py` warns when a `context.json` was produced against a lower version than the currently-loaded libraries. |
| `_comment` | string | no | Human note to future editors. Ignored by the loader. |
| `project_types` | object | yes | Keys are allowed project type strings. Values are arrays of strings. |

## Allowed `project_type` values

Both files MUST define an entry for each of these, **including `unknown`** (used as the fallback):

- `saas-dashboard`
- `marketing`
- `dev-tool`
- `internal-ops`
- `ecommerce`
- `creative`
- `game`
- `docs`
- `unknown`

If you add a new project type:
1. Add an entry with the same key to **both** `references.json` and `dimensions.json`.
2. Add a matching detection heuristic to `PROJECT_TYPE_HEURISTICS` in `scripts/discover.py`.
3. Add a default hero target to `DEFAULT_HERO_BY_TYPE` in `scripts/generate_prompt.py`.
4. Bump the `version` field in both JSON files.
5. Run `pytest tests/` and regenerate any fixture expected outputs that the new type affects.

## Per-type arrays

### `references.json → project_types.<type>`

- Type: `array<string>`, length: **exactly 5**
- Semantics: the five reference products for this project type, studied not copied
- Validator checks length == 5; `generate_prompt.py` trims/pads to 5 if overridden via `--refs` and warns when padding

### `dimensions.json → project_types.<type>`

- Type: `array<string>`, length: **5 to 10**
- Semantics: exploration dimensions the loop runner should pick 1–2 of per loop
- Each entry is a single line — no newlines, no markdown headings. Use the pattern `"<name> — <elaboration>"` for consistency with existing entries.

## When to bump `version`

Bump it when an edit would materially change the design direction any generated prompt takes:

- Adding or removing a reference from any project type
- Substituting one reference for another
- Adding or removing an exploration dimension
- Adding a new project type

Do **not** bump for:

- Typo fixes
- Rewording `_comment`
- Whitespace-only changes

## Version format

Use calendar versioning: `YYYY.MM` (e.g. `2026.04`). If you edit twice in one month and want them distinguishable, use `YYYY.MM.P` (e.g. `2026.04.2`). The comparison in `generate_prompt.py` is string-based, so zero-pad the patch.
