---
name: mvp-scope-guardian
version: 1.0.0
description: Locks an MVP definition by sorting every feature into four buckets (LAUNCH-BLOCKING / POST-LAUNCH V1.1 / PARKING LOT / WON'T BUILD) with effort/impact scoring, then provides ongoing scope creep detection. Triggers on "lock the scope", "prioritize features", "MVP scope review", "am I creeping scope", "should I add feature X", "is this scope creep", or "rescope the project". Part of the solo-dev-suite -- loads the project profile via the orchestrator. Not for greenfield brainstorming (use the brainstorming skill) or tech architecture decisions (use adr-generator).
---

# MVP Scope Guardian

Applies rigorous prioritization to a solo dev's feature list to produce a **locked MVP scope document** plus ongoing scope creep defense. Used by the solo-dev-suite.

## When to use this skill

- **Initial scope lock** -- user has a feature list (mental, in a doc, or scattered across chat history) and needs a defensible "this is what I'm building, nothing else" artifact.
- **Scope creep check** -- user says "I'm thinking about adding X" or "should I build Y" -- this skill compares against the locked scope and returns a verdict.
- **Rescope** -- user wants to legitimately change the locked scope due to new info (customer feedback, constraint change, pivot). Records the change + rationale.

## When NOT to use this skill

- **No profile exists** -- the orchestrator should be run first. This skill requires `profiles/<slug>.json` to exist.
- **Greenfield ideation** ("what should I build?") -- use the `brainstorming` skill. Scope Guardian needs an existing feature list as input.
- **Architecture or stack decisions** -- use `adr-generator`.
- **One-off code changes or bug fixes** -- just do the work.

## Prerequisites

- Project profile must exist: `solo-dev-suite/profiles/<slug>.json`
- Sidecar scope file lives at: `solo-dev-suite/profiles/<slug>.scope.json` (created by this skill on first `lock`)

## Operations

### 1. Lock (initial or full re-lock)

**Goal**: Produce the 4-bucket split of every feature the user is considering, with brutal honesty applied.

**Workflow**:

1. Load the profile (so you know the project's phase, launch target, hours/week, business model):
   ```bash
   python <SUITE_DIR>/scripts/profile_io.py show <slug> --json
   ```
2. If profile already has a sidecar scope file and user didn't say "re-lock", STOP and use `rescope` instead. Locking over an existing scope file destroys history.
3. Collect the feature list from the user. Accept any of: free-form list, pasted PRD, bullet list, or "walk me through it." For projects already in build phase, also ask what's **already built** so we can separate committed-reality from future-scope.
4. For each feature, run the **Three Killer Questions** in order (see below). Pre-assign a bucket based on the answers.
5. For every feature pre-assigned to `launch_blocking`, do an **effort/impact pass** (also below). Surface any feature that is high-effort AND low/medium-impact -- those are the top creep candidates to challenge.
6. Show the user the draft 4-bucket split with your reasoning. Invite override on any item. Iterate until they sign off.
7. Persist:
   ```bash
   echo '<scope_json>' | python scripts/scope_tool.py lock <slug> --from-stdin
   ```
   This writes the sidecar JSON, renders `MVP_SCOPE.md` and `MVP_PARKING_LOT.md`, and updates `last_skill_run.mvp-scope-guardian` on the profile.

**The Three Killer Questions** (apply to each feature):

1. **"Could a real paying customer live without this for 90 days post-launch?"**
   - If YES -> defaults to `post_launch_v1` or `parking_lot`. NOT launch-blocking.
   - If NO -> candidate for `launch_blocking`. Continue to Q2.
2. **"Does launching WITHOUT this make me look unprofessional, unsafe, or illegal?"**
   - Examples: auth, password reset, HTTPS, privacy policy, basic error handling, payment security for paid products.
   - If YES -> `launch_blocking`, no debate.
3. **"What would I REMOVE from the current LAUNCH-BLOCKING list to make room for this?"**
   - Forces trade-off thinking. If nothing, the feature is not actually launch-blocking -- user is in denial.

**Effort / Impact Pass**:

For each `launch_blocking` candidate, assign:

- **Effort**: S (<1 day), M (1-3 days), L (1-2 weeks), XL (2+ weeks).
- **Impact**: low / medium / high -- how much does this feature move the needle for the target user on launch day?

Flag for challenge any feature scoring:
- **L or XL effort + low or medium impact** -> "Is this really launch-blocking or can it slip to post-launch?"
- **Multiple XL features** in `launch_blocking` with a tight launch date -> "Your timeline math doesn't work. Cut or extend."

**Common solo-dev MVP traps** (apply as heuristics -- not rules):

- Admin dashboards -> almost always post_launch_v1. Use the database or logs for week 1.
- Analytics/reporting beyond Stripe + GA -> parking_lot until you have customers.
- Roles & permissions beyond "user vs admin" -> post_launch_v1.
- Onboarding tours / product tutorials -> post_launch_v1 (build them after you see where people get stuck).
- Notification preferences UI -> hardcode sensible defaults, UI is post_launch.
- Dark mode -> parking_lot. Every time.
- Multiple integrations at v1 -> pick ONE, defer the rest.
- Mobile apps when you also have web -> web-only at v1 unless the core use case is mobile-specific.
- Password reset SMS -> use email. SMS is post_launch.
- Localization / i18n -> parking_lot unless your target market is non-English from day one.

### 2. Show

Display the current locked scope in human-readable form.

```bash
python scripts/scope_tool.py show <slug>
```

### 3. Check (scope creep detection)

**Goal**: Given a candidate feature the user is *thinking about* adding, deliver a fast verdict.

**Workflow**:

1. Load sidecar:
   ```bash
   python scripts/scope_tool.py show <slug> --json
   ```
2. Compare the candidate feature against each bucket:
   - Match in `wont_build` (by name similarity or description overlap) -> 🛑 RED. Surface the original rationale for saying no.
   - Match in `post_launch_v1` or `parking_lot` -> 🟡 YELLOW. "This is already scoped, just not for launch. Pulling it forward costs you -- want to move it up with a trade?"
   - No match, truly new -> Run the Three Killer Questions inline and deliver a verdict: is this creep, or should it genuinely be added?
3. If user confirms they want to add it, offer two paths:
   - **Add with trade** -> run `rescope` to remove something from `launch_blocking` and add this
   - **Add to parking_lot** -> run `rescope` to just file it for later

Claude can invoke the check directly in conversation:

```bash
python scripts/scope_tool.py check <slug> --feature "feature name" --description "what it does"
```

But the real value is the conversation around the verdict -- the script just exposes the locked scope for comparison.

### 4. Rescope

**Goal**: Record a legitimate change to the locked scope with rationale, preserving history.

**Workflow**:

1. User explains what's changing and why.
2. Construct a patch that moves/adds/removes features across buckets.
3. Append a `rescope_history` entry: `{at, change, reason}`.
4. Persist:
   ```bash
   echo '<patch_json>' | python scripts/scope_tool.py rescope <slug> --from-stdin
   ```
5. Re-render the Markdown docs.

**Legitimate rescope triggers**:
- Customer discovery revealed a must-have you missed
- Technical constraint turned a must-have into a can't-have
- External dependency changed (pricing, deprecation)
- Launch target moved significantly (6+ weeks)

**NOT legitimate rescope triggers**:
- "I thought of a cool feature"
- "A competitor just shipped X"
- "It would be easy to add"
- "I'm bored with the current backlog"

If the user's reason falls in the second list, push back. Hard. That's the whole point of this skill.

### 5. Render

Re-generate the Markdown docs from the sidecar JSON. Useful after manual sidecar edits or when the template is updated.

```bash
python scripts/scope_tool.py render <slug> [--output-dir <path>]
```

Default output is `<repo>/docs/` if `repository_path` in the profile is accessible, otherwise `<suite>/profiles/<slug>_docs/`.

## Sidecar data shape

Authoritative schema: `templates/scope.schema.json`. Top-level keys:

- `schema_version` (integer, currently 1)
- `project_slug` (must match the profile)
- `locked_at` -- ISO timestamp of initial lock
- `last_rendered_at` -- ISO timestamp of last Markdown render
- `buckets.launch_blocking[]` -- features required for launch
- `buckets.post_launch_v1[]` -- features committed for the first post-launch wave
- `buckets.parking_lot[]` -- good ideas, not promised
- `buckets.wont_build[]` -- explicit NOs with rationale
- `rescope_history[]` -- ordered log of `{at, change, reason}` entries

Each feature in `launch_blocking` has: `id`, `name`, `description`, `effort`, `impact`, `rationale`.
Each feature in `post_launch_v1` has: `id`, `name`, `description`, `target_wave`.
Each feature in `parking_lot` has: `id`, `name`, `description`, `added_at`.
Each feature in `wont_build` has: `id`, `name`, `reason`.

IDs are prefixed: `LB01`, `PL01`, `PK01`, `WB01`. Auto-assigned by `scope_tool.py` on write.

## Output docs

Generated at `<output_dir>/` -- defaulting to `<repo>/docs/` when reachable:

- **`MVP_SCOPE.md`** -- the locked commitment. Launch-blocking features, explicit NOs, sign-off line.
- **`MVP_PARKING_LOT.md`** -- post-launch v1.1 queue, parking lot, promotion rules, rescope history.

These are meant to be committed to the repo. They're a contract with future-you.

## Files

```
mvp-scope-guardian/
├-- SKILL.md                          # this file
├-- scripts/
│   └-- scope_tool.py                 # lock / show / check / rescope / render
└-- templates/
    ├-- scope.schema.json             # JSON Schema for sidecar
    ├-- MVP_SCOPE.md.tmpl             # rendered locked doc
    └-- MVP_PARKING_LOT.md.tmpl       # rendered parking lot doc
```

## Testing

After changes to `scope_tool.py` or any template, run the smoke sequence:

```bash
# Use an existing profile (e.g. test-project) -- create via profile_io.py first
echo '{
  "buckets": {
    "launch_blocking": [{"name": "Auth", "description": "Email + password", "effort": "M", "impact": "high", "rationale": "Launch-blocking"}],
    "post_launch_v1": [{"name": "SSO", "description": "Google SSO", "target_wave": "v1.1"}],
    "parking_lot": [{"name": "Dark mode", "description": "Dark theme"}],
    "wont_build": [{"name": "Offline mode", "reason": "Overscoped -- web-only MVP"}]
  }
}' | python scripts/scope_tool.py lock test-project --from-stdin

python scripts/scope_tool.py show test-project
python scripts/scope_tool.py check test-project --feature "Offline mode" --description "works without internet"
```

Expected: lock succeeds, show renders the 4-bucket table, check surfaces the `wont_build` hit for "Offline mode" with the original reason.
