---
name: solo-dev-suite
version: 1.1.0
description: Master orchestrator for the Solo Dev Suite — a collection of lifecycle skills (scope guardian, sprint planner, pricing architect, launch readiness, ADR generator, security audit, integration mapper, auto-docs, tech debt register, testing strategy) that share a central Project Profile. Triggers on requests like "solo dev suite", "run the suite on {project}", "set up a project profile", "what suite skills apply here", "show my projects", or any direct invocation of a child skill by name when no profile exists yet. Not for one-off tasks with no ongoing project — those stay as standalone skills.
---

# Solo Dev Suite — Master Orchestrator

The Solo Dev Suite is a set of **10 child skills** that cover the full solo-developer lifecycle from locked scope through long-term sustainment. All children share a **central Project Profile registry** so you never have to re-establish context across skill invocations.

## When to use this skill

- User names a project and wants to work on it through the suite (e.g. "set up a project in the suite")
- User asks "what suite skills apply to my project right now?"
- User invokes a child skill by name — this orchestrator runs first to load or create the profile, then routes
- User asks to see/list/edit their project profiles

## When NOT to use this skill

- **Pre-project tasks** — valuation, market feasibility, brainstorming. Those are standalone and run *before* a project exists.
- **UI/UX exploration on a codebase** — use the standalone `design-loop` skill (it's codebase-aware, not profile-aware).
- **Feature enhancement on a specific feature** — use the standalone `feature-enhancement` skill.
- **One-off questions with no ongoing context** — just answer them.

## Child skills registry

The canonical list lives in `data/children.json`. Current roster:

| Skill | Phase(s) | Status |
|---|---|---|
| mvp-scope-guardian | scope | 🔜 planned |
| sprint-planner | build | 🔜 planned |
| saas-pricing-architect | scope, grow | 🔜 planned |
| launch-readiness | ship | 🔜 planned |
| integration-mapper | architecture, build | 🔜 planned |
| adr-generator | architecture, build | 🔜 planned |
| security-audit | ship | 🔜 planned |
| auto-docs | ship, sustain | 🔜 planned |
| tech-debt-register | build, sustain | 🔜 planned |
| testing-strategy | build | 🔜 planned |

Phases move left-to-right: `idea → scope → architecture → build → ship → grow → sustain`.

## Workflow

### 1. Determine intent

When triggered, figure out which of these the user wants:

- **A. Onboard a new project** → go to §2
- **B. Work on an existing project** → go to §3
- **C. List / show / edit profiles** → go to §4
- **D. Invoke a child skill directly** → load the profile first (§3), then route (§5)

If unclear, ask briefly. Don't run a questionnaire if the user just wants to see a list.

### 2. Onboard a new project (Profile creation)

Conduct a short, conversational interview — NOT a wall of questions. Ask them in logical groups, skip anything obvious from context. Target: **10 questions max, grouped into 3 passes.**

**Pass 1 — Identity (always ask):**
- Project name
- One-sentence description
- `project_slug` (auto-derive from name, confirm: kebab-case, used for filenames)

**Pass 2 — Shape (ask unless obvious):**
- `project_type` — one of: `saas`, `internal-tool`, `marketing-site`, `mobile-app`, `cli-tool`, `library`, `plugin`, `game`, `other`
- `primary_stack` — list of core tech (Next.js, Supabase, PostgreSQL, etc.)
- `hosting` — where it runs (homelab, Vercel, Cloudflare, AWS, self-hosted VPS, etc.)
- `repository_path` — absolute path to the code if it exists, or `null` if pre-code

**Pass 3 — Stakes & Constraints:**
- `target_users` — who uses it
- `business_model` — `saas-subscription`, `one-time-purchase`, `freemium`, `free-self-hosted`, `internal-only`, `undecided`
- `launch_target_date` — ISO date or `null`
- `available_hours_per_week` — realistic number, the developer has a day job
- `current_phase` — one of: `idea`, `scope`, `architecture`, `build`, `ship`, `grow`, `sustain`

Once answers are collected, build the JSON object per `templates/profile.schema.json` and persist:

```bash
echo '<json>' | python "<SKILL_DIR>/scripts/profile_io.py" init --from-stdin
```

Then confirm: display the profile back, ask if anything needs fixing, and show the phase-appropriate child skill menu (§5).

### 3. Load an existing project

If the user names a project, try to load its profile:

```bash
python "<SKILL_DIR>/scripts/profile_io.py" show <slug>
```

If found:
- Check `updated_at`. If older than 30 days, flag it: "Profile last touched {date} — phase may have drifted. Update? (y/n)"
- Surface the 3–5 most relevant fields inline so the user can see what context is loaded
- Proceed to the requested child skill (§5)

If NOT found, offer: "No profile for `{name}`. Want to onboard it? (y/n)" → if yes, go to §2.

If the user said a name that's close-but-not-exact to an existing slug, show a "did you mean?" list before offering onboarding.

### 4. List / show / edit profiles

```bash
# List all profiles
python "<SKILL_DIR>/scripts/profile_io.py" list

# Show a specific profile
python "<SKILL_DIR>/scripts/profile_io.py" show <slug>

# Update a profile (takes JSON patch on stdin)
echo '<patch>' | python "<SKILL_DIR>/scripts/profile_io.py" update <slug> --from-stdin
```

The update path uses a shallow merge — top-level keys in the patch replace top-level keys in the profile. For nested edits (e.g. adding to `third_party_services`), Claude should read the current profile, modify in memory, then write the full updated object.

### 5. Route to child skill

Two paths:

**A. Phase-appropriate menu** (when user asks "what can I run?"):

```bash
python "<SKILL_DIR>/scripts/list_skills.py" --phase <current_phase>
```

Displays only skills relevant to the current phase, marks `🔜 planned` vs `✅ active`.

**B. Direct invocation** (when user names a child skill):

1. Confirm profile is loaded
2. Inject the profile block at the top of the child skill's execution context (the child skill's `SKILL.md` declares where to read it from)
3. Hand off — the child skill takes over

Child skills read the profile with:

```bash
python "<SUITE_DIR>/scripts/profile_io.py" show <slug> --json
```

### 6. Record the run

After a child skill completes (or you're told it completed), update the profile's `last_skill_run` map:

```bash
echo '{"last_skill_run": {"<child_skill_name>": "<ISO_date>"}}' | \
  python "<SKILL_DIR>/scripts/profile_io.py" update <slug> --from-stdin
```

This keeps the staleness detector honest — e.g., "Scope Guardian ran 6 weeks ago, worth re-running given the new features."

## Profile schema

The authoritative schema is `templates/profile.schema.json`. Top-level keys:

- `project_name` — human-readable name (string)
- `project_slug` — kebab-case identifier for filenames (string)
- `description` — one sentence (string)
- `project_type` — enum (see §2)
- `primary_stack` — array of strings
- `hosting` — string
- `repository_path` — absolute path or null
- `target_users` — string
- `business_model` — enum (see §2)
- `pricing_model` — object or null (populated by saas-pricing-architect)
- `launch_target_date` — ISO date or null
- `available_hours_per_week` — integer
- `current_phase` — enum (see §2)
- `blockers` — array of strings (free-form notes, populated over time)
- `third_party_services` — array of `{name, purpose, risk_level}` objects (populated by integration-mapper)
- `last_skill_run` — object mapping child skill name → ISO timestamp
- `notes` — freeform string
- `created_at` — ISO timestamp (set on init)
- `updated_at` — ISO timestamp (set on every write)
- `schema_version` — integer, currently `1`

## Context window budget

This orchestrator stays **thin**. The actual work happens in children. If you find yourself inlining child skill logic here, stop — create or update the child skill file instead. The orchestrator's job is: load profile → route → record run. That's it.

## Files

```
solo-dev-suite/
├── SKILL.md                     # this file — master orchestrator
├── README.md                    # orientation doc for future-you
├── data/
│   └── children.json            # child skill registry (name, phases, status, triggers)
├── templates/
│   └── profile.schema.json      # JSON Schema for profile validation
├── scripts/
│   ├── profile_io.py            # init / show / list / update profiles
│   └── list_skills.py           # phase-aware child menu
└── profiles/
    └── <slug>.json              # per-project profiles (one file each)
```

## Tuning

- **Adding a new child skill** → create the skill folder separately, then add an entry to `data/children.json`. The orchestrator picks it up on the next `list_skills.py` run.
- **Schema migration** → bump `schema_version` in the schema AND in `profile_io.py`'s migration block. Add a migration function from the old version to the new.
- **New phase** → edit the `PHASES` tuple in `list_skills.py` and the enum in `profile.schema.json` together, or the validator will reject the new phase.

## Testing

Smoke test after any change to `profile_io.py`:

```bash
# Create a throwaway profile, read it back, delete it
echo '{"project_name":"Test","project_slug":"test","description":"x","project_type":"saas","primary_stack":["x"],"hosting":"x","repository_path":null,"target_users":"x","business_model":"undecided","pricing_model":null,"launch_target_date":null,"available_hours_per_week":1,"current_phase":"idea","blockers":[],"third_party_services":[],"last_skill_run":{},"notes":""}' \
  | python scripts/profile_io.py init --from-stdin
python scripts/profile_io.py show test
python scripts/profile_io.py list
rm profiles/test.json
```
