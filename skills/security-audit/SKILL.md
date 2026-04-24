---
name: security-audit
version: 1.0.0
description: Pre-ship security pass producing a prioritized findings list covering auth hardening, data exposure, secret management, and stack-specific checks. Triggers on "security audit", "security review", "security checklist", "am I leaking anything", "pre-ship security", or "check my security". Part of the solo-dev-suite -- loads the project profile via the orchestrator. Not a pentest -- a systematic "door-locked check" for solo devs.
---

# Security Audit

Runs a tailored pre-ship security pass. Not a pentest -- a systematic walk through the 20 things that actually bite solo devs year after year. Each item is a concrete yes/no question, not a security lecture.

## When to use this skill

- **Pre-launch security gate** -- before going live, walk the checklist to catch the obvious stuff.
- **Post-integration check** -- just added auth, payments, or file upload? Run the relevant category.
- **Periodic review** -- security posture changes as code evolves. Re-run quarterly.

## When NOT to use this skill

- **No profile exists** -- run the orchestrator first.
- **Actual penetration testing** -- this is a checklist, not a scanner. It doesn't read your code.
- **Third-party risk assessment** -- use integration-mapper for that. This checks how YOU use the service, not whether the service is risky.

## Prerequisites

- Project profile must exist: `solo-dev-suite/profiles/<slug>.json`
- Sidecar lives at: `solo-dev-suite/profiles/<slug>.security.json` (created by `init`)

## Methodology -- The Door-Locked Check

Solo dev security failures are rarely exotic. They're the same 20 things: hardcoded secrets, plaintext passwords, sessions that never expire, missing CSRF, no rate limiting, SQL injection, stored XSS, API keys in client JS, admin routes with no auth, debug mode in prod...

The audit walks 10 categories, each with concrete checkable items:

1. **Secret management** -- hardcoded secrets, env handling, .gitignore, key rotation
2. **Authentication** -- password hashing, session expiry, logout, reset tokens, email enumeration
3. **Input handling** -- SQL injection, XSS, file upload, user-controlled paths
4. **Transport & storage** -- HTTPS, cookie flags, at-rest encryption
5. **API surface** -- rate limits, auth on routes, CORS, input validation
6. **Frontend** -- client-side secrets, CSP, innerHTML usage, third-party scripts
7. **Infrastructure** -- admin UIs, debug mode, verbose errors, PII in logs
8. **Dependencies** -- known CVEs, supply chain trust
9. **Data handling** -- backup encryption, log retention, deletion, PII minimization
10. **Third-party integrations** -- webhook signatures, OAuth state params, per-service items

### Tailoring

Categories and items are dynamically adjusted based on:
- `primary_stack` -- React/FastAPI gets different items than Next.js/Supabase
- `project_type` -- marketing-site drops auth/payment categories
- `business_model` -- free-self-hosted drops payment items
- `third_party_services` -- Stripe adds webhook signature checks, OAuth services add state param validation

### Severity levels

- **critical** -- Ship-blocking. Your app is actively dangerous without this.
- **high** -- Should block ship. Serious exposure if left open.
- **medium** -- Fix soon after launch. Real risk but lower blast radius.
- **low** -- Nice to have. Defense in depth.

### The accepted-risk status

Some security items are genuinely risk-tradeoff decisions. Email enumeration on /forgot-password is a classic example -- fixing it degrades UX significantly, and for most solo apps the risk is acceptable.

Users can mark items as `accepted-risk` with a **required rationale**. The `check` command rejects `accepted-risk` without a rationale -- this is the structural version of "yeah but why."

Sign-off allows accepted-risk items -- they count as resolved.

### Sign-off gate

Sign-off requires:
- All **critical** items: passed, not-applicable, or accepted-risk
- All **high** items: passed, not-applicable, or accepted-risk
- `--force` bypasses with a loud warning (for genuinely urgent ships)

## Operations

### 1. Init (build tailored checklist)

```bash
python scripts/security_tool.py init <slug>
```

Reads the profile, builds a tailored checklist, persists the sidecar. Run once per audit cycle.

### 2. Show (view checklist)

```bash
python scripts/security_tool.py show <slug>
python scripts/security_tool.py show <slug> --category secrets
python scripts/security_tool.py show <slug> --json
```

Human-readable output with status icons and severity tags.

### 3. Check (mark a single item)

```bash
python scripts/security_tool.py check <slug> --item SEC01 --status passed
python scripts/security_tool.py check <slug> --item AUTH03 --status accepted-risk --risk-rationale "Email enumeration acceptable for this app"
```

Status values: `passed`, `failed`, `not-applicable`, `accepted-risk`, `not-checked`.
`accepted-risk` requires `--risk-rationale` or the command fails.

### 4. Sign-off (gate on open items)

```bash
python scripts/security_tool.py sign-off <slug> --signed-by "Developer"
python scripts/security_tool.py sign-off <slug> --signed-by "Developer" --force
```

Blocks if any critical or high items are still open (not-checked or failed). `--force` bypasses.

### 5. Render

```bash
python scripts/security_tool.py render <slug> [--output-dir <path>]
```

Generates `SECURITY_AUDIT.md` with findings summary, per-category detail, and accepted risks section.

### 6. Delete

```bash
python scripts/security_tool.py delete <slug> [--yes]
```

Removes the sidecar. Profile mirror NOT cleared.

## Sidecar data shape

Authoritative schema: `templates/security.schema.json`.

## Profile mirror

After every sidecar write, `profile.security_model` is updated:
```json
{
  "last_audit_at": "...",
  "criticals_open": 2,
  "highs_open": 5,
  "accepted_risks": 1,
  "is_signed_off": false
}
```

Also updates `last_skill_run["security-audit"]`.

## Output docs

`<repo>/docs/SECURITY_AUDIT.md` -- findings summary, per-category detail, accepted risks.

## Files

```
security-audit/
├── SKILL.md                              # this file
├── scripts/
│   └── security_tool.py                  # init / show / check / sign-off / render / delete
└── templates/
    ├── security.schema.json              # JSON Schema for sidecar
    └── SECURITY_AUDIT.md.tmpl            # rendered doc template
```

## Testing

```bash
python scripts/security_tool.py init my-project
python scripts/security_tool.py show my-project
python scripts/security_tool.py check my-project --item SEC01 --status passed
python scripts/security_tool.py check my-project --item AUTH03 --status accepted-risk
python scripts/security_tool.py check my-project --item AUTH03 --status accepted-risk --risk-rationale "Email enumeration on /forgot-password accepted"
python scripts/security_tool.py sign-off my-project --signed-by "Developer"
python scripts/security_tool.py render my-project
python scripts/security_tool.py delete my-project --yes
```

Expected: init tailors for SaaS/React/FastAPI profile, accepted-risk without rationale fails, sign-off blocks on open criticals/highs, render produces findings doc, delete cleans up sidecar.
