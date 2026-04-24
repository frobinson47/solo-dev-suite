#!/usr/bin/env python3
"""
quickstart.py -- Project auto-detection for Solo Dev Suite onboarding.

Scans a project directory, detects stack, frameworks, hosting config,
and project maturity. Outputs a pre-filled profile JSON so Claude only
needs to ask for the fields that can't be detected automatically.

Commands:
    detect  <path> [--json]    # scan and report findings

Exit codes:
    0  success
    1  path does not exist
    2  path is not a directory

Design notes:
  * No external deps. Pure stdlib. Same patterns as profile_io.py.
  * Detection is best-effort. Missing data is null, not guessed.
  * The script does NOT create a profile — it outputs what it found
    so the orchestrator can fill gaps conversationally.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_DIR = SCRIPT_DIR.parent


def _err(msg: str) -> None:
    print(f"[quickstart] {msg}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# Detection helpers                                                           #
# --------------------------------------------------------------------------- #

def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    """Safely read a JSON file. Returns None on any failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_text(path: Path) -> Optional[str]:
    """Safely read a text file."""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _slugify(name: str) -> str:
    """Convert a project name to a kebab-case slug."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or "my-project"


def _git_commit_count(project_path: Path) -> Optional[int]:
    """Get the number of git commits. Returns None if not a git repo."""
    git_dir = project_path / ".git"
    if not git_dir.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(project_path),
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------- #
# Stack detection                                                             #
# --------------------------------------------------------------------------- #

# Maps dependency names to human-readable stack entries
NODE_DEPS = {
    "react": "React", "react-dom": "React",
    "next": "Next.js", "nuxt": "Nuxt",
    "vue": "Vue", "svelte": "Svelte", "solid-js": "SolidJS",
    "express": "Express", "fastify": "Fastify", "hono": "Hono",
    "tailwindcss": "Tailwind CSS", "@tailwindcss/postcss": "Tailwind CSS",
    "vite": "Vite", "webpack": "Webpack", "esbuild": "esbuild",
    "typescript": "TypeScript",
    "prisma": "Prisma", "@prisma/client": "Prisma",
    "drizzle-orm": "Drizzle ORM",
    "@supabase/supabase-js": "Supabase",
    "stripe": "Stripe",
    "socket.io": "Socket.IO",
}

PYTHON_DEPS = {
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
    "uvicorn": "Uvicorn", "sqlalchemy": "SQLAlchemy",
    "celery": "Celery", "redis": "Redis",
    "boto3": "AWS SDK", "httpx": "httpx",
}


def _detect_node(project_path: Path) -> Tuple[List[str], Optional[str]]:
    """Detect Node.js stack from package.json. Returns (stack_items, project_name)."""
    pkg = _read_json(project_path / "package.json")
    if not pkg:
        return [], None

    name = pkg.get("name")
    stack: Set[str] = set()

    all_deps = {}
    all_deps.update(pkg.get("dependencies", {}))
    all_deps.update(pkg.get("devDependencies", {}))

    for dep, label in NODE_DEPS.items():
        if dep in all_deps:
            # Try to extract version for major frameworks
            ver = all_deps[dep].lstrip("^~>=<")
            major = ver.split(".")[0] if ver and ver[0].isdigit() else None
            if dep in ("react", "next", "vue") and major:
                stack.add(f"{label} {major}")
            else:
                stack.add(label)

    if not stack:
        stack.add("Node.js")

    return sorted(stack), name


def _detect_python(project_path: Path) -> Tuple[List[str], Optional[str]]:
    """Detect Python stack from requirements.txt or pyproject.toml."""
    stack: Set[str] = set()
    name = None

    # pyproject.toml
    pyproject = _read_text(project_path / "pyproject.toml")
    if pyproject:
        for dep, label in PYTHON_DEPS.items():
            if dep in pyproject.lower():
                stack.add(label)
        name_match = re.search(r'name\s*=\s*"([^"]+)"', pyproject)
        if name_match:
            name = name_match.group(1)

    # requirements.txt
    reqs = _read_text(project_path / "requirements.txt")
    if reqs:
        for line in reqs.splitlines():
            dep = re.split(r'[>=<\[!]', line.strip().lower())[0]
            if dep in PYTHON_DEPS:
                stack.add(PYTHON_DEPS[dep])

    if stack or reqs or pyproject:
        stack.add("Python")

    return sorted(stack), name


def _detect_rust(project_path: Path) -> Tuple[List[str], Optional[str]]:
    """Detect Rust stack from Cargo.toml."""
    cargo = _read_text(project_path / "Cargo.toml")
    if not cargo:
        return [], None

    name = None
    name_match = re.search(r'name\s*=\s*"([^"]+)"', cargo)
    if name_match:
        name = name_match.group(1)

    stack: Set[str] = {"Rust"}
    known = {
        "actix-web": "Actix Web", "axum": "Axum", "rocket": "Rocket",
        "tokio": "Tokio", "serde": "Serde", "diesel": "Diesel",
        "sqlx": "SQLx", "reqwest": "Reqwest",
    }
    for dep, label in known.items():
        if dep in cargo:
            stack.add(label)

    return sorted(stack), name


def _detect_go(project_path: Path) -> Tuple[List[str], Optional[str]]:
    """Detect Go stack from go.mod."""
    gomod = _read_text(project_path / "go.mod")
    if not gomod:
        return [], None

    name = None
    mod_match = re.search(r'^module\s+(\S+)', gomod, re.MULTILINE)
    if mod_match:
        name = mod_match.group(1).split("/")[-1]

    stack: Set[str] = {"Go"}
    known = {
        "gin-gonic/gin": "Gin", "gorilla/mux": "Gorilla Mux",
        "labstack/echo": "Echo", "gofiber/fiber": "Fiber",
        "gorm.io/gorm": "GORM",
    }
    for dep, label in known.items():
        if dep in gomod:
            stack.add(label)

    return sorted(stack), name


def _detect_ruby(project_path: Path) -> Tuple[List[str], Optional[str]]:
    """Detect Ruby stack from Gemfile."""
    gemfile = _read_text(project_path / "Gemfile")
    if not gemfile:
        return [], None

    stack: Set[str] = {"Ruby"}
    if "rails" in gemfile.lower():
        stack.add("Rails")

    return sorted(stack), None


def _detect_java(project_path: Path) -> Tuple[List[str], Optional[str]]:
    """Detect Java stack from pom.xml or build.gradle."""
    stack: Set[str] = set()
    name = None

    pom = _read_text(project_path / "pom.xml")
    if pom:
        stack.add("Java")
        if "spring-boot" in pom:
            stack.add("Spring Boot")
        name_match = re.search(r'<artifactId>([^<]+)</artifactId>', pom)
        if name_match:
            name = name_match.group(1)

    gradle = _read_text(project_path / "build.gradle")
    if gradle:
        stack.add("Java")
        if "spring" in gradle.lower():
            stack.add("Spring Boot")

    return sorted(stack), name


def _detect_php(project_path: Path) -> Tuple[List[str], Optional[str]]:
    """Detect PHP stack from composer.json."""
    composer = _read_json(project_path / "composer.json")
    if not composer:
        return [], None

    name = composer.get("name")
    stack: Set[str] = {"PHP"}

    all_deps = {}
    all_deps.update(composer.get("require", {}))
    all_deps.update(composer.get("require-dev", {}))

    known = {
        "laravel/framework": "Laravel", "symfony/symfony": "Symfony",
        "slim/slim": "Slim",
    }
    for dep, label in known.items():
        if dep in all_deps:
            stack.add(label)

    return sorted(stack), name


# --------------------------------------------------------------------------- #
# Hosting detection                                                           #
# --------------------------------------------------------------------------- #

def _detect_hosting(project_path: Path) -> Optional[str]:
    """Detect hosting platform from config files."""
    checks = [
        ("vercel.json", "Vercel"),
        ("netlify.toml", "Netlify"),
        ("wrangler.toml", "Cloudflare Workers"),
        ("fly.toml", "Fly.io"),
        ("render.yaml", "Render"),
        ("railway.toml", "Railway"),
        ("railway.json", "Railway"),
        ("app.yaml", "Google App Engine"),
        ("Procfile", "Heroku"),
    ]
    for filename, platform in checks:
        if (project_path / filename).exists():
            return platform

    # Docker implies self-hosted
    if (project_path / "docker-compose.yml").exists() or (project_path / "docker-compose.yaml").exists():
        return "Docker / self-hosted"
    if (project_path / "Dockerfile").exists():
        return "Docker"

    return None


# --------------------------------------------------------------------------- #
# Database detection                                                          #
# --------------------------------------------------------------------------- #

def _detect_database(project_path: Path) -> List[str]:
    """Detect databases from config files and dependencies."""
    dbs: Set[str] = set()

    # Check package.json deps
    pkg = _read_json(project_path / "package.json")
    if pkg:
        all_deps = {}
        all_deps.update(pkg.get("dependencies", {}))
        all_deps.update(pkg.get("devDependencies", {}))
        db_deps = {
            "pg": "PostgreSQL", "mysql2": "MySQL", "better-sqlite3": "SQLite",
            "mongodb": "MongoDB", "mongoose": "MongoDB", "redis": "Redis",
            "@supabase/supabase-js": "Supabase (PostgreSQL)",
        }
        for dep, label in db_deps.items():
            if dep in all_deps:
                dbs.add(label)

    # Check for .env references
    env_file = _read_text(project_path / ".env") or _read_text(project_path / ".env.example")
    if env_file:
        if "DATABASE_URL" in env_file or "DB_HOST" in env_file:
            if "postgres" in env_file.lower():
                dbs.add("PostgreSQL")
            elif "mysql" in env_file.lower() or "maria" in env_file.lower():
                dbs.add("MySQL/MariaDB")
            elif "sqlite" in env_file.lower():
                dbs.add("SQLite")

    return sorted(dbs)


# --------------------------------------------------------------------------- #
# Phase inference                                                             #
# --------------------------------------------------------------------------- #

def _infer_phase(project_path: Path) -> Tuple[Optional[str], str]:
    """Infer project phase from git history and file presence.
    Returns (phase, reason)."""
    has_git = (project_path / ".git").exists()
    has_scope = (project_path / "docs" / "MVP_SCOPE.md").exists()
    has_adr = (project_path / "docs" / "adr").exists()
    has_launch = (project_path / "docs" / "LAUNCH_READINESS.md").exists()
    has_security = (project_path / "docs" / "SECURITY_AUDIT.md").exists()
    commits = _git_commit_count(project_path)

    if has_launch or has_security:
        return "ship", "launch/security docs exist"
    if commits and commits >= 100:
        return "build", f"{commits} commits, mature codebase"
    if has_scope:
        return "build", "MVP_SCOPE.md exists, scope locked"
    if has_adr:
        return "architecture", "ADR docs exist"
    if commits and commits >= 20:
        return "build", f"{commits} commits"
    if commits and commits >= 5:
        return "architecture", f"{commits} commits, early development"
    if has_git:
        return "scope", "git repo initialized, few commits"
    return "idea", "no git history detected"


# --------------------------------------------------------------------------- #
# Project type inference                                                      #
# --------------------------------------------------------------------------- #

def _infer_project_type(stack: List[str], project_path: Path) -> Optional[str]:
    """Infer project_type from detected stack."""
    stack_lower = {s.lower() for s in stack}

    # CLI tool
    if (project_path / "bin").exists() or any("cli" in s for s in stack_lower):
        return "cli-tool"

    # Library/package
    pkg = _read_json(project_path / "package.json")
    if pkg and pkg.get("main") and not pkg.get("scripts", {}).get("dev"):
        return "library"

    # Web frameworks suggest SaaS or internal tool
    web_frameworks = {"react", "next.js", "vue", "nuxt", "svelte", "django", "flask",
                      "fastapi", "rails", "laravel", "express", "spring boot"}
    if stack_lower & web_frameworks:
        return "saas"  # default for web apps; user can correct

    return None


# --------------------------------------------------------------------------- #
# Main detection                                                              #
# --------------------------------------------------------------------------- #

def detect_project(project_path: Path) -> Dict[str, Any]:
    """Run all detectors and assemble a pre-filled profile."""

    # Stack detection — try all ecosystems, merge results
    all_stack: List[str] = []
    project_name = None

    detectors = [
        _detect_node, _detect_python, _detect_rust,
        _detect_go, _detect_ruby, _detect_java, _detect_php,
    ]

    # Scan root AND common subdirectories (frontend/, backend/, client/, server/, src/, app/)
    scan_dirs = [project_path]
    for sub in ("frontend", "backend", "client", "server", "src", "app", "web"):
        sub_path = project_path / sub
        if sub_path.is_dir():
            scan_dirs.append(sub_path)

    for scan_dir in scan_dirs:
        for detector in detectors:
            stack, name = detector(scan_dir)
            all_stack.extend(stack)
            # Only use detected name from root dir, not subdirectories
            if name and not project_name and scan_dir == project_path:
                project_name = name

    # Detect bare PHP projects (*.php files without composer.json)
    if not any("PHP" in s for s in all_stack):
        php_files = list(project_path.glob("*.php"))
        if php_files:
            all_stack.append("PHP")
            # Check for common PHP patterns
            api_dir = project_path / "api"
            if api_dir.is_dir() and list(api_dir.glob("*.php")):
                all_stack.append("PHP REST API")

    # Deduplicate stack
    seen: Set[str] = set()
    unique_stack: List[str] = []
    for item in all_stack:
        if item.lower() not in seen:
            seen.add(item.lower())
            unique_stack.append(item)

    # Fall back to directory name for project name
    if not project_name:
        project_name = project_path.name

    # Databases
    databases = _detect_database(project_path)
    if databases:
        unique_stack.extend(db for db in databases if db.lower() not in seen)

    # Hosting
    hosting = _detect_hosting(project_path)

    # Phase
    phase, phase_reason = _infer_phase(project_path)

    # Project type
    project_type = _infer_project_type(unique_stack, project_path)

    slug = _slugify(project_name)

    return {
        "detected": {
            "project_name": project_name,
            "project_slug": slug,
            "primary_stack": unique_stack or None,
            "hosting": hosting,
            "current_phase": phase,
            "phase_reason": phase_reason,
            "project_type": project_type,
            "repository_path": str(project_path),
            "databases": databases or None,
        },
        "needs_input": {
            "description": None,
            "target_users": None,
            "business_model": None,
            "available_hours_per_week": None,
            "launch_target_date": None,
        },
        "path": str(project_path),
    }


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_detect(args: argparse.Namespace) -> int:
    """Scan a project directory and report findings."""
    project_path = Path(args.path).resolve()

    if not project_path.exists():
        _err(f"Path does not exist: {project_path}")
        return 1
    if not project_path.is_dir():
        _err(f"Path is not a directory: {project_path}")
        return 2

    result = detect_project(project_path)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    d = result["detected"]
    n = result["needs_input"]

    print(f"\n  Detected from {project_path}:\n")

    print(f"  Name      : {d['project_name']}")
    print(f"  Slug      : {d['project_slug']}")

    if d["primary_stack"]:
        print(f"  Stack     : {', '.join(d['primary_stack'])}")
    else:
        print(f"  Stack     : (not detected)")

    if d["project_type"]:
        print(f"  Type      : {d['project_type']}")
    else:
        print(f"  Type      : (not detected)")

    if d["hosting"]:
        print(f"  Hosting   : {d['hosting']}")
    else:
        print(f"  Hosting   : (not detected)")

    print(f"  Phase     : {d['current_phase']} ({d['phase_reason']})")
    print(f"  Repo      : {d['repository_path']}")

    # Show what still needs asking
    missing = [k.replace("_", " ") for k, v in n.items() if v is None]
    if missing:
        print(f"\n  Still needed: {', '.join(missing)}")

    print()
    return 0


# --------------------------------------------------------------------------- #
# Arg parsing                                                                 #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quickstart",
        description="Auto-detect project characteristics for Solo Dev Suite onboarding.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_detect = sub.add_parser("detect", help="Scan a project directory.")
    p_detect.add_argument("path", help="Path to the project directory.")
    p_detect.add_argument("--json", action="store_true", help="Machine-readable output.")
    p_detect.set_defaults(func=cmd_detect)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
