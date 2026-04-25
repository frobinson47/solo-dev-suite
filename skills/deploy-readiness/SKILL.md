---
name: deploy-readiness
version: 1.0.0
description: Scans a codebase for local-to-cloud migration blockers -- hardcoded paths, LAN URLs, dev-only bypasses, missing deploy configs -- and produces a scored readiness report. Triggers on "deploy readiness", "ready to deploy", "can I host this", "cloud migration check", "scan for local stuff", "deployment blockers". Part of the solo-dev-suite -- loads the project profile via the orchestrator. Unlike security-audit (a checklist), this skill actually reads code.
---

# Deploy Readiness

Scans a codebase for things that will break when you move from local development to cloud hosting. Not a checklist -- an automated scanner that reads your code and reports concrete findings with file paths and line numbers.

## When to use this skill

- **Pre-deployment gate** -- before moving a locally-developed project to cloud hosting
- **After major changes** -- just added new integrations, config, or infrastructure? Re-scan.
- **Periodic review** -- local assumptions creep in over time. Re-scan quarterly.
- **Cloud migration planning** -- inventory everything that needs to change before hosting.

## When NOT to use this skill

- **No profile exists** -- run the orchestrator first.
- **Security vulnerabilities** -- use security-audit for that. This checks portability, not safety.
- **Already cloud-hosted** -- if the app is already deployed and working in the cloud, this skill adds no value.
- **Third-party risk assessment** -- use integration-mapper for that.

## Prerequisites

- Project profile must exist: `solo-dev-suite/profiles/<slug>.json`
- Profile must have `repository_path` set (or use `--path` override)

## What it scans

8 categories, each targeting a specific class of local-to-cloud blocker:

1. **Hardcoded URLs** -- `.fmr.local`, `.local` hostnames, `localhost`, `127.0.0.1`, private/LAN IPs (192.168.x.x, 10.x.x.x)
2. **Hardcoded paths** -- `D:\laragon\...`, `C:\xampp\...`, `/home/user/...` absolute paths
3. **Development bypasses** -- `APP_ENV === 'development'` gates, hardcoded test credentials (`admin/admin`)
4. **Missing deploy config** -- no Dockerfile, no CI/CD, no `.env.example`
5. **Database configuration** -- empty passwords, root user, hardcoded ports
6. **CORS origins** -- wildcard `*` or localhost-only CORS policies
7. **Local file storage** -- `move_uploaded_file`, `writeFileSync` to local upload dirs
8. **Environment secrets** -- API keys/tokens hardcoded in source files

### Scoring

- Starts at 100, deducts per unresolved finding
- critical = -10, high = -5, medium = -2, low = -1
- Labels: READY (90+), ALMOST (70-89), NEEDS WORK (40-69), NOT READY (<40)

### What it skips

- `node_modules/`, `vendor/`, `.git/`, `dist/`, `build/`, `__pycache__/`
- Binary files and files > 512KB
- Lock files (`package-lock.json`, `*.lock`)

## Operations

### 1. Scan (read the codebase)

```bash
python scripts/deploy_readiness_tool.py scan <slug>
python scripts/deploy_readiness_tool.py scan <slug> --path /alternate/repo
python scripts/deploy_readiness_tool.py scan <slug> --json
```

Walks the repo, scans every source file, checks repo structure, writes the sidecar. Re-running overwrites the previous scan.

### 2. Show (view findings)

```bash
python scripts/deploy_readiness_tool.py show <slug>
python scripts/deploy_readiness_tool.py show <slug> --category hardcoded-urls
python scripts/deploy_readiness_tool.py show <slug> --json
```

Human-readable output with status icons, severity tags, file:line locations, and matched code.

### 3. Resolve (mark findings)

```bash
python scripts/deploy_readiness_tool.py resolve <slug> --item URL01
python scripts/deploy_readiness_tool.py resolve <slug> --item URL01 --status wont-fix --notes "Dev-only config file"
```

Status values: `resolved`, `wont-fix`. Recalculates the score after each resolution.

### 4. Render

```bash
python scripts/deploy_readiness_tool.py render <slug> [--output-dir <path>]
```

Generates `DEPLOY_READINESS.md` with summary table, per-category findings, and severity indicators.

### 5. Delete

```bash
python scripts/deploy_readiness_tool.py delete <slug> --yes
```

Removes the sidecar.

## Profile mirror

After every scan, `profile.deploy_readiness_model` is updated:
```json
{
  "last_scan_at": "...",
  "score": 72,
  "score_label": "ALMOST",
  "total_findings": 15,
  "criticals": 2,
  "highs": 4
}
```

Also updates `last_skill_run["deploy-readiness"]`.

## Files

```
deploy-readiness/
├── SKILL.md                              # this file
├── .claude-plugin/
│   └── plugin.json                       # plugin metadata
└── scripts/
    └── deploy_readiness_tool.py          # scan / show / resolve / render / delete
```

## Testing

```bash
python scripts/deploy_readiness_tool.py scan my-project
python scripts/deploy_readiness_tool.py scan my-project --path D:/laragon/www/crumble
python scripts/deploy_readiness_tool.py show my-project
python scripts/deploy_readiness_tool.py show my-project --category hardcoded-urls
python scripts/deploy_readiness_tool.py resolve my-project --item URL01
python scripts/deploy_readiness_tool.py render my-project
python scripts/deploy_readiness_tool.py delete my-project --yes
```

Expected: scan finds .fmr.local, localhost, D:\laragon paths in typical local-dev projects. Score reflects severity. Resolve marks items and recalculates.
