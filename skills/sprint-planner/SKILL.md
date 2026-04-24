---
name: sprint-planner
version: 1.0.0
description: Converts a backlog into realistic solo-dev sprints accounting for day job + family + surprise maintenance -- with velocity tracking, launch countdown, and honest capacity math.
---

# sprint-planner

## When to use

- Starting the build phase and need to break work into manageable chunks.
- After locking scope (mvp-scope-guardian) to plan the execution order.
- Weekly sprint check-ins to update progress and plan the next sprint.
- Checking if you're on track for a launch date.

## When NOT to use

- For generating actual task code (this plans the work, doesn't do it).
- For project-level planning beyond sprints (use mvp-scope-guardian for scope).
- If the project has no defined work items yet.

## Prerequisites

- Project must be onboarded in solo-dev-suite.
- `available_hours_per_week` should be set honestly in the profile.
- Ideally, scope is locked first so you know what needs building.

## Methodology

### Honest capacity, not aspirational capacity

The buffer_percent (default 20%) accounts for real life: day job emergencies, family commitments, infra fires, meetings that should have been emails. If you set it to 0%, you're lying to yourself.

**Effective hours = hours_per_week x sprint_length_weeks x (1 - buffer_percent/100)**

### Velocity is earned, not estimated

Until you complete a sprint, you have zero velocity data. The tool tracks actual hours completed per sprint and averages them. Your first sprint estimate will be wrong -- that's the point. By sprint 3, you'll have honest numbers.

### Launch countdown: red/yellow/green

If `launch_target_date` is set in the profile, the tool compares remaining backlog hours against remaining sprint capacity:
- **Green**: remaining work <= 80% of available capacity (comfortable buffer)
- **Yellow**: remaining work <= 100% of available capacity (tight but possible)
- **Red**: remaining work > available capacity (something has to give)

### Incomplete items return to backlog

When you complete a sprint, any todo/in-progress items automatically return to the backlog with priority bumped to "high" (you committed to them once -- they matter). Dropped items stay in the sprint record for the retro.

## Operations

### init

Set up capacity and optional initial backlog.

```
echo '{"hours_per_week": 10, "sprint_length_weeks": 2, "buffer_percent": 20, "backlog": [{"title": "User auth", "estimate_hours": 12, "priority": "critical", "category": "feature"}, {"title": "API endpoints", "estimate_hours": 8, "priority": "high"}]}' | python scripts/sprint_tool.py init <slug> --from-stdin
```

`hours_per_week` defaults to profile's `available_hours_per_week` if omitted.

### add

Add items to the backlog.

```
echo '{"items": [{"title": "Payment webhook handler", "estimate_hours": 6, "priority": "high", "category": "feature"}]}' | python scripts/sprint_tool.py add <slug> --from-stdin
```

Single item shorthand (no `items` wrapper) also works.

### plan

Plan the next sprint by pulling items from the backlog.

```
echo '{"goal": "Core auth + API scaffold", "backlog_ids": ["BL01", "BL02"]}' | python scripts/sprint_tool.py plan <slug> --from-stdin
```

Warns if planned hours exceed 120% of sprint capacity. Won't plan if there's an active sprint.

### start

Activate the next planned sprint.

```
python scripts/sprint_tool.py start <slug>
```

### update

Update item statuses and actual hours in the active sprint.

```
echo '{"items": [{"id": "SI01", "status": "done", "actual_hours": 10}, {"id": "SI02", "status": "in-progress"}]}' | python scripts/sprint_tool.py update <slug> --from-stdin
```

### complete

Complete the active sprint. Computes velocity, returns incomplete items to backlog.

```
python scripts/sprint_tool.py complete <slug> --retro "Auth took longer than expected, need to buffer more for OAuth flows"
```

### show

Display current state: capacity, velocity, launch countdown, active sprint, backlog.

```
python scripts/sprint_tool.py show <slug>
python scripts/sprint_tool.py show <slug> --json
```

### render

Generate SPRINT_PLAN.md.

```
python scripts/sprint_tool.py render <slug>
```

### delete

Remove sidecar.

```
python scripts/sprint_tool.py delete <slug> --yes
```

## Files

| File | Purpose |
|------|---------|
| `scripts/sprint_tool.py` | CLI with all subcommands |
| `templates/sprint.schema.json` | Sidecar JSON Schema |
| `templates/SPRINT_PLAN.md.tmpl` | Rendered doc template |
