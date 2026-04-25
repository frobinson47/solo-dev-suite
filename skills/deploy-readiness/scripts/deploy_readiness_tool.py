#!/usr/bin/env python3
"""
deploy_readiness_tool.py -- Codebase scanner for local-to-cloud migration blockers.

Unlike security-audit (a checklist), this skill actually reads code and
reports concrete findings with file paths and line numbers.

Commands:
    scan     <slug> [--path <dir>] [--json]     # Scan codebase, write sidecar
    show     <slug> [--category <id>] [--json]   # Display findings
    resolve  <slug> --item <ID> [--notes ...]    # Mark a finding resolved
    render   <slug> [--output-dir <path>]        # Generate DEPLOY_READINESS.md
    delete   <slug> [--yes]                      # Remove sidecar

Categories scanned:
    hardcoded-urls     .fmr.local, localhost, 127.0.0.1, LAN IPs
    hardcoded-paths    D:\\, C:\\, /home/, absolute OS paths in source
    dev-bypasses       APP_ENV=development checks, dev-only login, test credentials
    missing-deploy     No Dockerfile, no CI config, no production env template
    db-config          Hardcoded DB passwords (or lack thereof), localhost connections
    cors-origins       CORS allowing localhost or wildcard origins
    file-storage       Local disk writes (uploads/, tmp/) without abstraction
    env-secrets        Secrets in source instead of env vars

Exit codes:
    0  success (scan complete, may have findings)
    1  slug/profile not found
    2  suite install broken
    3  no repository_path in profile
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = SKILL_DIR / "templates"


def _find_suite_dir() -> Path:
    env = os.environ.get("SOLO_DEV_SUITE_DIR")
    if env:
        p = Path(env).resolve()
        if p.is_dir():
            return p
    sibling = SKILL_DIR.parent / "solo-dev-suite"
    if sibling.is_dir():
        return sibling
    for ancestor in SKILL_DIR.parents:
        candidate = ancestor / "solo-dev-suite"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not find solo-dev-suite directory.")


SUITE_DIR = _find_suite_dir()
PROFILES_DIR = SUITE_DIR / "profiles"


def _err(msg: str) -> None:
    print(f"[deploy_readiness] {msg}", file=sys.stderr)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _human_date(iso: Optional[str]) -> str:
    if not iso:
        return "(not set)"
    try:
        dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%B %d, %Y at %H:%M UTC")
    except ValueError:
        return iso


def _profile_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.json"


def _sidecar_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.deploy-readiness.json"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _err(f"{path} is corrupted: {e}")
        sys.exit(2)


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_profile(slug: str) -> Dict[str, Any]:
    p = _profile_path(slug)
    profile = _read_json(p)
    if profile is None:
        _err(f"No profile for slug '{slug}'.")
        sys.exit(1)
    return profile


def _load_sidecar(slug: str) -> Dict[str, Any]:
    sidecar = _read_json(_sidecar_path(slug))
    if sidecar is None:
        _err(f"No deploy-readiness scan for '{slug}'. Run `deploy_readiness_tool.py scan {slug}` first.")
        sys.exit(1)
    return sidecar


# --------------------------------------------------------------------------- #
# File scanning engine                                                        #
# --------------------------------------------------------------------------- #

# Extensions to scan (source code, config, not binaries)
SCAN_EXTENSIONS = {
    ".php", ".js", ".jsx", ".ts", ".tsx", ".py", ".rb", ".go", ".rs",
    ".json", ".yml", ".yaml", ".toml", ".env", ".env.example",
    ".conf", ".cfg", ".ini", ".xml", ".sql", ".sh", ".bash",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".md", ".txt", ".htaccess",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "vendor", "dist", "build", "__pycache__",
    ".next", ".nuxt", ".cache", ".vscode", ".idea", "coverage",
    "fe-output", ".claude-plugin",
}

# Max file size to scan (512KB)
MAX_FILE_SIZE = 512 * 1024

# Max findings per category to prevent noise
MAX_FINDINGS_PER_CAT = 50


Finding = Dict[str, Any]


def _scan_file(file_path: Path, repo_root: Path) -> List[Tuple[str, Finding]]:
    """Scan a single file for deployment blockers. Returns [(category, finding)]."""
    results: List[Tuple[str, Finding]] = []
    rel = str(file_path.relative_to(repo_root)).replace("\\", "/")

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return results

    lines = content.split("\n")

    for line_num, line in enumerate(lines, start=1):
        line_stripped = line.strip()

        # --- HARDCODED URLs ---
        # .fmr.local, .local domains
        if re.search(r'\b\w+\.fmr\.local\b', line, re.IGNORECASE):
            results.append(("hardcoded-urls", {
                "file": rel, "line": line_num,
                "match": line_stripped[:120],
                "severity": "critical",
                "detail": "LAN hostname (.fmr.local) -- will not resolve outside local network",
            }))
        elif re.search(r'\b\w+\.local\b', line, re.IGNORECASE):
            # .local but not .fmr.local (already caught above)
            if not re.search(r'\.locale\b|localStorage|localForage|localeCompare|localName', line):
                results.append(("hardcoded-urls", {
                    "file": rel, "line": line_num,
                    "match": line_stripped[:120],
                    "severity": "high",
                    "detail": ".local hostname -- likely LAN-only",
                }))

        # localhost / 127.0.0.1
        if re.search(r'(?:localhost|127\.0\.0\.1)(?::\d+)?', line):
            # Skip lock files and common false positives
            if not any(skip in rel for skip in ["node_modules", "package-lock", ".lock"]):
                if not re.search(r'(//|#)\s*(dev|local|example|test)', line, re.IGNORECASE):
                    results.append(("hardcoded-urls", {
                        "file": rel, "line": line_num,
                        "match": line_stripped[:120],
                        "severity": "high",
                        "detail": "localhost reference -- needs environment-based URL",
                    }))

        # LAN IPs (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
        if re.search(r'\b(?:192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b', line):
            results.append(("hardcoded-urls", {
                "file": rel, "line": line_num,
                "match": line_stripped[:120],
                "severity": "critical",
                "detail": "Private/LAN IP address -- unreachable from cloud",
            }))

        # --- HARDCODED PATHS ---
        # Windows drive letters
        if re.search(r'["\']?[A-Z]:\\(?:laragon|xampp|wamp|Users|home)', line, re.IGNORECASE):
            results.append(("hardcoded-paths", {
                "file": rel, "line": line_num,
                "match": line_stripped[:120],
                "severity": "critical",
                "detail": "Absolute Windows path -- not portable to cloud hosting",
            }))

        # Unix absolute paths to home/user dirs
        if re.search(r'["\']?/(?:home|Users)/\w+/', line):
            if not line_stripped.startswith("#"):
                results.append(("hardcoded-paths", {
                    "file": rel, "line": line_num,
                    "match": line_stripped[:120],
                    "severity": "high",
                    "detail": "Absolute home directory path -- not portable",
                }))

        # --- DEV BYPASSES ---
        # APP_ENV / NODE_ENV development checks that bypass auth/features
        if re.search(r'(?:APP_ENV|NODE_ENV)\s*(?:===?|==|!=)\s*["\'](?:development|dev|local)["\']', line):
            results.append(("dev-bypasses", {
                "file": rel, "line": line_num,
                "match": line_stripped[:120],
                "severity": "high",
                "detail": "Environment-gated code path -- verify behavior in production mode",
            }))

        # Hardcoded test/dev credentials
        if re.search(r'(?:password|passwd|pass)\s*(?:=|:)\s*["\'](?:admin|password|test|123|root|secret)["\']', line, re.IGNORECASE):
            results.append(("dev-bypasses", {
                "file": rel, "line": line_num,
                "match": line_stripped[:120],
                "severity": "critical",
                "detail": "Hardcoded credential -- must use env var or secrets manager",
            }))

        # --- DB CONFIG ---
        # Empty password / no-password database connections
        if re.search(r'(?:DB_PASSWORD|MYSQL_PASSWORD|POSTGRES_PASSWORD|database\.password)\s*(?:=|:)\s*["\']?\s*["\']?\s*$', line, re.IGNORECASE):
            results.append(("db-config", {
                "file": rel, "line": line_num,
                "match": line_stripped[:120],
                "severity": "critical",
                "detail": "Empty database password -- must be set for production",
            }))

        # root user without password
        if re.search(r'(?:DB_USERNAME|DB_USER|MYSQL_USER)\s*(?:=|:)\s*["\']?root["\']?', line, re.IGNORECASE):
            results.append(("db-config", {
                "file": rel, "line": line_num,
                "match": line_stripped[:120],
                "severity": "high",
                "detail": "Database root user -- use a least-privilege user in production",
            }))

        # Hardcoded DB port (3306/3307/5432)
        if re.search(r'(?:DB_PORT|database\.port)\s*(?:=|:)\s*["\']?(?:3306|3307|5432)["\']?', line, re.IGNORECASE):
            results.append(("db-config", {
                "file": rel, "line": line_num,
                "match": line_stripped[:120],
                "severity": "low",
                "detail": "Hardcoded DB port -- should come from env var for managed DB services",
            }))

        # --- CORS ORIGINS ---
        if re.search(r'(?:Access-Control-Allow-Origin|cors.*origin)\s*(?:=|:).*(?:\*|localhost|\.local)', line, re.IGNORECASE):
            results.append(("cors-origins", {
                "file": rel, "line": line_num,
                "match": line_stripped[:120],
                "severity": "high",
                "detail": "CORS origin allows localhost/wildcard -- restrict to production domain(s)",
            }))

        # --- FILE STORAGE ---
        # Direct file writes to upload dirs
        if re.search(r'(?:move_uploaded_file|file_put_contents|writeFileSync|fs\.write)\s*\(', line):
            if re.search(r'(?:upload|tmp|temp|storage)', line, re.IGNORECASE):
                results.append(("file-storage", {
                    "file": rel, "line": line_num,
                    "match": line_stripped[:120],
                    "severity": "high",
                    "detail": "Local disk write for uploads -- needs object storage (S3/R2) in cloud",
                }))

        # --- ENV SECRETS ---
        # API keys / tokens hardcoded in source (not .env)
        if not rel.endswith((".env", ".env.example", ".env.local")):
            if re.search(r'(?:api_key|apikey|api_secret|secret_key|auth_token)\s*(?:=|:)\s*["\'][a-zA-Z0-9_\-]{20,}["\']', line, re.IGNORECASE):
                results.append(("env-secrets", {
                    "file": rel, "line": line_num,
                    "match": line_stripped[:40] + "...",  # truncate to avoid leaking the key
                    "severity": "critical",
                    "detail": "Possible API key/secret hardcoded in source -- use env var",
                }))

    return results


def _scan_repo_structure(repo_root: Path) -> List[Tuple[str, Finding]]:
    """Check for missing deployment infrastructure files."""
    results: List[Tuple[str, Finding]] = []

    # Missing Dockerfile
    has_dockerfile = (repo_root / "Dockerfile").exists() or (repo_root / "docker-compose.yml").exists()
    has_deploy_config = any((repo_root / f).exists() for f in [
        "fly.toml", "vercel.json", "wrangler.toml", "render.yaml",
        "railway.json", "Procfile", "app.yaml", "netlify.toml",
    ])
    if not has_dockerfile and not has_deploy_config:
        results.append(("missing-deploy", {
            "file": "(project root)",
            "line": 0,
            "match": "",
            "severity": "high",
            "detail": "No Dockerfile or deploy config found -- needs deployment configuration",
        }))

    # Missing CI/CD
    has_ci = any([
        (repo_root / ".github" / "workflows").is_dir(),
        (repo_root / ".gitlab-ci.yml").exists(),
        (repo_root / "Jenkinsfile").exists(),
        (repo_root / ".circleci").is_dir(),
    ])
    if not has_ci:
        results.append(("missing-deploy", {
            "file": "(project root)",
            "line": 0,
            "match": "",
            "severity": "medium",
            "detail": "No CI/CD configuration found -- needs automated build/deploy pipeline",
        }))

    # Missing .env.example / .env.production template
    has_env_template = any((repo_root / f).exists() for f in [
        ".env.example", ".env.template", ".env.production.example",
    ])
    if not has_env_template:
        results.append(("missing-deploy", {
            "file": "(project root)",
            "line": 0,
            "match": "",
            "severity": "medium",
            "detail": "No .env.example or .env.template -- document required environment variables",
        }))

    # .env committed (not in .gitignore)
    gitignore = repo_root / ".gitignore"
    if gitignore.exists():
        gi_content = gitignore.read_text(encoding="utf-8", errors="replace")
        if ".env" not in gi_content:
            if (repo_root / ".env").exists():
                results.append(("env-secrets", {
                    "file": ".gitignore",
                    "line": 0,
                    "match": "",
                    "severity": "critical",
                    "detail": ".env file exists but not in .gitignore -- secrets may be committed",
                }))

    return results


def _collect_files(repo_root: Path) -> List[Path]:
    """Walk the repo and collect scannable files."""
    files = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Skip excluded directories (in-place modification)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        dp = Path(dirpath)
        for fname in filenames:
            fp = dp / fname
            # Check extension
            suffix = fp.suffix.lower()
            # Also scan extensionless files like Dockerfile, Makefile, Procfile
            if suffix in SCAN_EXTENSIONS or fname in (
                "Dockerfile", "Makefile", "Procfile", "Caddyfile",
                ".htaccess", ".gitignore", ".dockerignore",
            ):
                try:
                    if fp.stat().st_size <= MAX_FILE_SIZE:
                        files.append(fp)
                except OSError:
                    continue
    return files


# --------------------------------------------------------------------------- #
# Scoring                                                                     #
# --------------------------------------------------------------------------- #

SEVERITY_SCORES = {"critical": 10, "high": 5, "medium": 2, "low": 1}


def _compute_score(categories: List[Dict[str, Any]]) -> int:
    """Compute deploy-readiness score (0-100, higher = more ready).
    Starts at 100, deducts for each unresolved finding."""
    total_deductions = 0
    for cat in categories:
        for finding in cat.get("findings", []):
            if finding.get("status") != "resolved":
                total_deductions += SEVERITY_SCORES.get(finding["severity"], 1)
    return max(0, 100 - total_deductions)


def _score_label(score: int) -> str:
    if score >= 90:
        return "READY"
    elif score >= 70:
        return "ALMOST"
    elif score >= 40:
        return "NEEDS WORK"
    else:
        return "NOT READY"


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

CATEGORY_NAMES = {
    "hardcoded-urls": "Hardcoded URLs",
    "hardcoded-paths": "Hardcoded paths",
    "dev-bypasses": "Development bypasses",
    "missing-deploy": "Missing deploy config",
    "db-config": "Database configuration",
    "cors-origins": "CORS origins",
    "file-storage": "Local file storage",
    "env-secrets": "Environment secrets",
}

CATEGORY_PREFIXES = {
    "hardcoded-urls": "URL",
    "hardcoded-paths": "PTH",
    "dev-bypasses": "DEV",
    "missing-deploy": "DPL",
    "db-config": "DB",
    "cors-origins": "COR",
    "file-storage": "FS",
    "env-secrets": "SEC",
}


def cmd_scan(args: argparse.Namespace) -> int:
    """Scan a codebase for deployment blockers."""
    slug = args.slug
    profile = _load_profile(slug)

    # Determine repo path
    repo_path = args.path or profile.get("repository_path")
    if not repo_path:
        _err(f"No repository_path in profile and no --path given.")
        return 3
    repo_root = Path(repo_path).resolve()
    if not repo_root.is_dir():
        _err(f"Repository path does not exist: {repo_root}")
        return 3

    print(f"\n  Scanning: {repo_root}")

    # Collect files
    files = _collect_files(repo_root)
    print(f"  Files to scan: {len(files)}")

    # Scan files
    raw_findings: Dict[str, List[Finding]] = {cat: [] for cat in CATEGORY_NAMES}

    for fp in files:
        for cat, finding in _scan_file(fp, repo_root):
            if cat in raw_findings and len(raw_findings[cat]) < MAX_FINDINGS_PER_CAT:
                raw_findings[cat].append(finding)

    # Scan repo structure
    for cat, finding in _scan_repo_structure(repo_root):
        if cat in raw_findings:
            raw_findings[cat].append(finding)

    # Build categories with assigned IDs
    categories = []
    for cat_id, cat_name in CATEGORY_NAMES.items():
        findings = raw_findings.get(cat_id, [])
        prefix = CATEGORY_PREFIXES[cat_id]
        for i, f in enumerate(findings, start=1):
            f["id"] = f"{prefix}{i:02d}"
            f["status"] = "open"
        categories.append({
            "id": cat_id,
            "name": cat_name,
            "findings": findings,
        })

    # Build sidecar
    now = _now_iso()
    total = sum(len(c["findings"]) for c in categories)
    criticals = sum(1 for c in categories for f in c["findings"] if f["severity"] == "critical")
    highs = sum(1 for c in categories for f in c["findings"] if f["severity"] == "high")
    score = _compute_score(categories)

    sidecar = {
        "schema_version": 1,
        "project_slug": slug,
        "scanned_path": str(repo_root),
        "scanned_at": now,
        "updated_at": now,
        "files_scanned": len(files),
        "total_findings": total,
        "score": score,
        "score_label": _score_label(score),
        "categories": categories,
    }

    _write_json_atomic(_sidecar_path(slug), sidecar)

    # Update profile
    profile["deploy_readiness_model"] = {
        "last_scan_at": now,
        "score": score,
        "score_label": _score_label(score),
        "total_findings": total,
        "criticals": criticals,
        "highs": highs,
    }
    if "last_skill_run" not in profile:
        profile["last_skill_run"] = {}
    profile["last_skill_run"]["deploy-readiness"] = now
    _write_json_atomic(_profile_path(slug), profile)

    if args.json:
        print(json.dumps(sidecar, indent=2))
        return 0

    # Human-readable summary
    print(f"  Score: {score}/100 ({_score_label(score)})")
    print(f"  Findings: {total} total, {criticals} critical, {highs} high\n")

    for cat in categories:
        if not cat["findings"]:
            continue
        sev_counts = {}
        for f in cat["findings"]:
            sev_counts[f["severity"]] = sev_counts.get(f["severity"], 0) + 1
        sev_str = ", ".join(f"{v} {k}" for k, v in sorted(sev_counts.items(),
                           key=lambda x: ["critical","high","medium","low"].index(x[0])))
        print(f"  {cat['name']}: {len(cat['findings'])} findings ({sev_str})")

    print()
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Display scan findings."""
    slug = args.slug
    sidecar = _load_sidecar(slug)

    if args.json:
        if args.category:
            for cat in sidecar["categories"]:
                if cat["id"] == args.category:
                    print(json.dumps(cat, indent=2))
                    return 0
            _err(f"Category '{args.category}' not found.")
            return 1
        print(json.dumps(sidecar, indent=2))
        return 0

    profile = _load_profile(slug)
    project_name = profile.get("project_name", slug)
    score = sidecar.get("score", 0)

    print(f"\n  {project_name} ({slug}) -- Deploy Readiness")
    print(f"  Score: {score}/100 ({_score_label(score)})")
    print(f"  Scanned: {_human_date(sidecar.get('scanned_at'))}")
    print(f"  Files: {sidecar.get('files_scanned', 0)}")
    print(f"  {'-' * 55}\n")

    _STATUS_ICON = {"open": "[X]", "resolved": "[+]", "wont-fix": "[!]"}
    _SEVERITY_TAG = {
        "critical": "[CRITICAL]",
        "high": "[HIGH]",
        "medium": "[MEDIUM]",
        "low": "[LOW]",
    }

    for cat in sidecar["categories"]:
        if args.category and cat["id"] != args.category:
            continue
        if not cat["findings"]:
            continue

        print(f"  --- {cat['name']} ---")
        for f in cat["findings"]:
            icon = _STATUS_ICON.get(f.get("status", "open"), "[?]")
            sev = _SEVERITY_TAG.get(f["severity"], "")
            loc = f"{f['file']}:{f['line']}" if f["line"] > 0 else f["file"]
            print(f"  {icon}  {f['id']}  {sev}  {loc}")
            print(f"        {f['detail']}")
            if f.get("match"):
                print(f"        > {f['match'][:100]}")
        print()

    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    """Mark a finding as resolved or wont-fix."""
    slug = args.slug
    sidecar = _load_sidecar(slug)
    item_id = args.item
    new_status = args.status

    for cat in sidecar["categories"]:
        for f in cat["findings"]:
            if f["id"] == item_id:
                old = f.get("status", "open")
                f["status"] = new_status
                if args.notes:
                    f["notes"] = args.notes
                sidecar["score"] = _compute_score(sidecar["categories"])
                sidecar["score_label"] = _score_label(sidecar["score"])
                sidecar["updated_at"] = _now_iso()
                _write_json_atomic(_sidecar_path(slug), sidecar)
                print(f"  {item_id}: {old} -> {new_status} (score: {sidecar['score']}/100)")
                return 0

    _err(f"Finding '{item_id}' not found.")
    return 1


def cmd_render(args: argparse.Namespace) -> int:
    """Render DEPLOY_READINESS.md."""
    slug = args.slug
    sidecar = _load_sidecar(slug)
    profile = _load_profile(slug)
    project_name = profile.get("project_name", slug)

    # Resolve output dir
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    if not output_dir:
        repo = profile.get("repository_path")
        if repo and Path(repo).is_dir():
            output_dir = Path(repo) / "docs"
        else:
            output_dir = PROFILES_DIR / f"{slug}_docs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "DEPLOY_READINESS.md"

    score = sidecar.get("score", 0)
    total = sidecar.get("total_findings", 0)
    criticals = sum(1 for c in sidecar["categories"] for f in c["findings"]
                    if f["severity"] == "critical" and f.get("status") != "resolved")
    highs = sum(1 for c in sidecar["categories"] for f in c["findings"]
                if f["severity"] == "high" and f.get("status") != "resolved")

    lines = [
        f"> **Deploy Readiness Scan** for **{project_name}** (`{slug}`)",
        ">",
        f"> Do not edit this file by hand. Re-scan with `deploy_readiness_tool.py scan {slug}`.",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Score | {score}/100 ({_score_label(score)}) |",
        f"| Scanned | {_human_date(sidecar.get('scanned_at'))} |",
        f"| Files scanned | {sidecar.get('files_scanned', 0)} |",
        f"| Total findings | {total} |",
        f"| Criticals open | {criticals} |",
        f"| Highs open | {highs} |",
        "",
    ]

    if criticals > 0:
        lines.append(f"> **{criticals} CRITICAL finding(s) must be resolved before deployment.**")
        lines.append("")
    if highs > 0:
        lines.append(f"> **{highs} HIGH finding(s) should be resolved before deployment.**")
        lines.append("")

    lines.extend(["---", "", "## Findings by Category", ""])

    _STATUS_ICON = {"open": "[ ]", "resolved": "[x]", "wont-fix": "[!]"}

    for cat in sidecar["categories"]:
        if not cat["findings"]:
            continue
        lines.append(f"### {cat['name']}")
        lines.append("")
        lines.append("| Status | ID | Severity | Location | Detail |")
        lines.append("|--------|----|----------|----------|--------|")
        for f in cat["findings"]:
            icon = _STATUS_ICON.get(f.get("status", "open"), "[ ]")
            loc = f"`{f['file']}:{f['line']}`" if f["line"] > 0 else f"`{f['file']}`"
            detail = f["detail"].replace("|", "\\|")
            lines.append(f"| {icon} | `{f['id']}` | {f['severity']} | {loc} | {detail} |")
        lines.append("")

    lines.extend([
        "---",
        "",
        f"_Generated by `deploy-readiness` -- Re-scan with `python scripts/deploy_readiness_tool.py scan {slug}`_",
        "",
    ])

    md = "\n".join(lines)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(md, encoding="utf-8")
    tmp.replace(output_path)

    print(f"  Rendered: {output_path}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete the deploy-readiness sidecar."""
    sp = _sidecar_path(args.slug)
    if not sp.exists():
        _err(f"No deploy-readiness scan for '{args.slug}'.")
        return 1
    if not args.yes:
        _err(f"Pass --yes to confirm deletion of {sp}.")
        return 1
    sp.unlink()
    print(f"  Deleted deploy-readiness sidecar for '{args.slug}'.")
    return 0


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deploy_readiness_tool",
        description="Scan codebase for local-to-cloud deployment blockers.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("scan", help="Scan codebase for blockers.")
    sp.add_argument("slug", help="Project slug.")
    sp.add_argument("--path", help="Override repository path (default: profile.repository_path).")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("show", help="Display scan findings.")
    sp.add_argument("slug", help="Project slug.")
    sp.add_argument("--category", help="Filter to one category.")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("resolve", help="Mark a finding resolved or wont-fix.")
    sp.add_argument("slug", help="Project slug.")
    sp.add_argument("--item", required=True, help="Finding ID (e.g. URL01).")
    sp.add_argument("--status", default="resolved", choices=["resolved", "wont-fix"])
    sp.add_argument("--notes", default="", help="Resolution notes.")
    sp.set_defaults(func=cmd_resolve)

    sp = sub.add_parser("render", help="Generate DEPLOY_READINESS.md.")
    sp.add_argument("slug", help="Project slug.")
    sp.add_argument("--output-dir", help="Override output directory.")
    sp.set_defaults(func=cmd_render)

    sp = sub.add_parser("delete", help="Delete sidecar.")
    sp.add_argument("slug", help="Project slug.")
    sp.add_argument("--yes", action="store_true")
    sp.set_defaults(func=cmd_delete)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
