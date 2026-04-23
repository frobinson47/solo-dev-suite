#!/usr/bin/env python3
"""
discover.py — FMR Feature Enhancement Skill
Deep codebase scanner: extracts stack, features, deps, TODOs, stubs, and incomplete work.
Emits a single JSON context blob for downstream phases.

Usage:
    python discover.py <target_path> [--forgejo-url <url>] [--output <path>]
"""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────

# Files/dirs that signal a specific language or framework
FRAMEWORK_SIGNALS = {
    "next.js":        ["next.config.js", "next.config.mjs", "next.config.ts"],
    "nuxt":           ["nuxt.config.js", "nuxt.config.ts"],
    "react":          [],    # detected via package.json dep
    "vue":            [],
    "svelte":         ["svelte.config.js"],
    "astro":          ["astro.config.mjs", "astro.config.ts"],
    "angular":        ["angular.json"],
    "django":         ["manage.py", "settings.py"],
    "flask":          [],    # detected via requirements.txt
    "fastapi":        [],
    "laravel":        ["artisan", "composer.json"],
    "rails":          ["Gemfile", "config/routes.rb"],
    "spring":         ["pom.xml", "build.gradle"],
    "express":        [],    # via package.json
    "nestjs":         [],
    "dotnet":         [],    # via .csproj
    "wordpress":      ["wp-config.php", "wp-login.php"],
    "electron":       [],
    "tauri":          ["tauri.conf.json", "src-tauri"],
}

# Package manifest files to parse for dependencies
MANIFEST_FILES = {
    "package.json":      "node",
    "requirements.txt":  "python",
    "pyproject.toml":    "python",
    "Pipfile":           "python",
    "Gemfile":           "ruby",
    "pom.xml":           "java",
    "build.gradle":      "java",
    "go.mod":            "go",
    "Cargo.toml":        "rust",
    "composer.json":     "php",
    "*.csproj":          "dotnet",
    "*.fsproj":          "dotnet",
}

# Patterns that indicate an incomplete or stub feature
STUB_PATTERNS = [
    (r"#\s*(TODO|FIXME|HACK|XXX|STUB|WIP|BROKEN|INCOMPLETE|NOTIMPLEMENTED)",  "comment"),
    (r"//\s*(TODO|FIXME|HACK|XXX|STUB|WIP|BROKEN|INCOMPLETE|NOTIMPLEMENTED)", "comment"),
    (r"/\*\s*(TODO|FIXME|HACK|XXX|STUB|WIP|BROKEN)",                          "comment"),
    (r"raise\s+NotImplementedError",                                           "python_stub"),
    (r"throw\s+new\s+(NotImplemented|Error)\(",                                "js_stub"),
    (r"pass\s*$",                                                              "python_pass"),
    (r"return\s+null;?\s*//.*TODO",                                            "null_stub"),
    (r"console\.log\([\"']TODO",                                               "log_stub"),
    (r"placeholder",                                                           "placeholder"),
    (r"Coming\s+soon",                                                         "coming_soon"),
    (r"Not\s+implemented",                                                     "not_implemented"),
    (r"lorem\s+ipsum",                                                         "lorem"),
    (r"\{\s*\/\*\s*(stub|placeholder|todo)\s*\*\/\s*\}",                       "jsx_stub"),
]

# Route/feature detection patterns per framework type
ROUTE_PATTERNS = {
    "nextjs_pages":  r"pages/(.+?)\.(tsx?|jsx?)",
    "nextjs_app":    r"app/(.+?)/(page|route)\.(tsx?|jsx?)",
    "express_route": r"\.(get|post|put|delete|patch)\(['\"](.+?)['\"]",
    "django_url":    r"path\(['\"](.+?)['\"]",
    "flask_route":   r"@\w+\.route\(['\"](.+?)['\"]",
    "rails_route":   r"(get|post|put|delete|patch|resources)\s+['\"]?(.+?)['\"]?",
    "fastapi_route": r"@\w+\.(get|post|put|delete|patch)\(['\"](.+?)['\"]",
    "vue_router":    r"path:\s*['\"](.+?)['\"]",
    "react_router":  r"<Route\s+path=['\"](.+?)['\"]",
}

# Extensions to scan for features/stubs (skip binaries, lock files, dist)
SCAN_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".py", ".rb", ".php", ".java",
    ".cs", ".go", ".rs", ".vue", ".svelte", ".astro", ".html",
    ".css", ".scss", ".sass", ".less",
}

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "__pycache__",
    ".venv", "venv", "vendor", "target", "bin", "obj", ".cache",
    "coverage", ".nyc_output", "public/static", "static/dist",
    "migrations", ".forgejo", ".github",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def safe_read(path: Path, max_bytes: int = 500_000) -> str:
    """Read a file safely, returning empty string on failure."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)
    except Exception:
        return ""


def file_line_count(path: Path) -> int:
    """Count lines in a file without loading it fully."""
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


# ─── Dependency / Stack Detection ─────────────────────────────────────────────

def parse_package_json(root: Path) -> dict:
    """Extract deps, devDeps, scripts from package.json."""
    pj = root / "package.json"
    if not pj.exists():
        return {}
    try:
        data = json.loads(safe_read(pj))
        deps = list(data.get("dependencies", {}).keys())
        dev  = list(data.get("devDependencies", {}).keys())
        return {
            "runtime": deps,
            "dev":     dev,
            "scripts": list(data.get("scripts", {}).keys()),
            "name":    data.get("name", ""),
            "version": data.get("version", ""),
        }
    except Exception:
        return {}


def parse_requirements(root: Path) -> list:
    """Parse requirements.txt into a dep list."""
    reqs = root / "requirements.txt"
    if not reqs.exists():
        return []
    lines = safe_read(reqs).splitlines()
    return [l.split("==")[0].split(">=")[0].strip()
            for l in lines if l.strip() and not l.startswith("#")]


def parse_pyproject(root: Path) -> dict:
    """Basic pyproject.toml dep extraction without toml library."""
    pp = root / "pyproject.toml"
    if not pp.exists():
        return {}
    content = safe_read(pp)
    # Grab [tool.poetry.dependencies] or [project] dependencies sections
    deps = re.findall(r'^([a-zA-Z0-9_\-]+)\s*=', content, re.MULTILINE)
    return {"runtime": deps}


def detect_languages(root: Path) -> list:
    """Count file extensions to determine primary languages."""
    counts = defaultdict(int)
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in SCAN_EXTENSIONS:
            # skip large ignored dirs
            parts = set(p.parts)
            if parts & SKIP_DIRS:
                continue
            counts[p.suffix] += 1
    sorted_langs = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"ext": ext, "count": cnt} for ext, cnt in sorted_langs[:10]]


def detect_frameworks(root: Path, pkg: dict) -> list:
    """Detect frameworks from file signals and package deps."""
    detected = []
    all_deps = set(pkg.get("runtime", []) + pkg.get("dev", []))

    # Check file-based signals
    for fw, signals in FRAMEWORK_SIGNALS.items():
        for sig in signals:
            if (root / sig).exists():
                detected.append(fw)
                break

    # Check node dep signals
    dep_fw_map = {
        "next":        "next.js",
        "react":       "react",
        "vue":         "vue",
        "@angular/core": "angular",
        "svelte":      "svelte",
        "astro":       "astro",
        "express":     "express",
        "@nestjs/core": "nestjs",
        "electron":    "electron",
        "nuxt":        "nuxt",
    }
    for dep, fw in dep_fw_map.items():
        if dep in all_deps and fw not in detected:
            detected.append(fw)

    # Check Python requirements
    py_reqs = parse_requirements(root)
    py_fw_map = {
        "django":  "django",
        "flask":   "flask",
        "fastapi": "fastapi",
        "tornado": "tornado",
        "starlette": "starlette",
    }
    for dep, fw in py_fw_map.items():
        if dep in py_reqs and fw not in detected:
            detected.append(fw)

    # dotnet check
    csproj = list(root.rglob("*.csproj"))
    if csproj:
        detected.append("dotnet/csharp")

    # WordPress
    if (root / "wp-config.php").exists() or (root / "wp-login.php").exists():
        detected.append("wordpress")

    return list(set(detected))


def detect_databases(root: Path, pkg: dict) -> list:
    """Detect database integrations from deps and config files."""
    dbs = []
    all_deps = set(pkg.get("runtime", []) + pkg.get("dev", []))
    py_reqs  = set(parse_requirements(root))

    db_signals = {
        "postgres":  ["pg", "postgres", "postgresql", "psycopg2", "asyncpg"],
        "mysql":     ["mysql", "mysql2", "mysqlclient", "pymysql"],
        "sqlite":    ["sqlite3", "better-sqlite3", "sqlite"],
        "mongodb":   ["mongoose", "mongodb", "motor", "pymongo"],
        "redis":     ["redis", "ioredis", "aioredis"],
        "supabase":  ["@supabase/supabase-js", "supabase"],
        "prisma":    ["prisma", "@prisma/client"],
        "drizzle":   ["drizzle-orm"],
        "typeorm":   ["typeorm"],
        "sqlalchemy":["sqlalchemy"],
        "firebase":  ["firebase", "firebase-admin"],
        "planetscale":["@planetscale/database"],
    }
    combined = all_deps | py_reqs
    for db, signals in db_signals.items():
        if any(s in combined for s in signals):
            dbs.append(db)
    return dbs


def detect_auth(root: Path, pkg: dict) -> list:
    """Detect authentication solutions."""
    auths = []
    all_deps = set(pkg.get("runtime", []) + pkg.get("dev", []))
    auth_signals = {
        "next-auth":    ["next-auth"],
        "auth.js":      ["@auth/core"],
        "clerk":        ["@clerk/nextjs", "@clerk/clerk-react"],
        "supabase-auth":["@supabase/auth-helpers-nextjs"],
        "firebase-auth":["firebase"],
        "passport":     ["passport", "passport-local", "passport-jwt"],
        "jwt":          ["jsonwebtoken", "jose"],
        "oauth2":       ["oauth2"],
        "keycloak":     ["keycloak-js"],
        "auth0":        ["@auth0/auth0-react", "auth0"],
    }
    for auth, signals in auth_signals.items():
        if any(s in all_deps for s in signals):
            auths.append(auth)
    return auths


# ─── Feature / Route Detection ────────────────────────────────────────────────

def detect_routes(root: Path, frameworks: list) -> list:
    """Extract routes/pages from the codebase."""
    routes = []
    seen   = set()

    # Next.js pages dir
    pages_dir = root / "pages"
    if pages_dir.exists():
        for p in pages_dir.rglob("*.tsx"):
            rel = str(p.relative_to(pages_dir))
            route = "/" + rel.replace("\\", "/").replace(".tsx", "").replace("/index", "")
            if route not in seen:
                routes.append({"path": route, "type": "page", "file": str(p.relative_to(root))})
                seen.add(route)

    # Next.js app dir
    app_dir = root / "app"
    if app_dir.exists():
        for p in app_dir.rglob("page.tsx"):
            rel = str(p.parent.relative_to(app_dir))
            route = "/" + rel.replace("\\", "/") if rel != "." else "/"
            if route not in seen:
                routes.append({"path": route, "type": "page", "file": str(p.relative_to(root))})
                seen.add(route)
        for p in app_dir.rglob("route.ts"):
            rel = str(p.parent.relative_to(app_dir))
            route = "/api/" + rel.replace("\\", "/") if rel != "." else "/api"
            if route not in seen:
                routes.append({"path": route, "type": "api", "file": str(p.relative_to(root))})
                seen.add(route)

    # Scan source files for inline route patterns
    for scan_file in root.rglob("*"):
        if not scan_file.is_file():
            continue
        parts = set(scan_file.parts)
        if parts & SKIP_DIRS:
            continue
        if scan_file.suffix not in {".py", ".js", ".ts", ".rb", ".php"}:
            continue
        content = safe_read(scan_file)
        for pattern_name, pattern in ROUTE_PATTERNS.items():
            for match in re.finditer(pattern, content):
                grps = match.groups()
                path = grps[-1] if grps else ""
                if path and path not in seen and len(path) < 120:
                    routes.append({
                        "path":    path,
                        "type":    "route",
                        "source":  pattern_name,
                        "file":    str(scan_file.relative_to(root)),
                    })
                    seen.add(path)
    return routes[:200]   # cap for sanity


def detect_components(root: Path) -> list:
    """Find component files in common component directories."""
    component_dirs = ["components", "src/components", "app/components",
                      "lib/components", "ui", "src/ui", "views", "src/views"]
    components = []
    for cdir in component_dirs:
        cpath = root / cdir
        if not cpath.exists():
            continue
        for p in cpath.rglob("*"):
            if p.is_file() and p.suffix in {".tsx", ".jsx", ".vue", ".svelte"}:
                name = p.stem
                # Skip index, layout, barrel files
                if name.lower() not in {"index", "layout", "_app", "_document"}:
                    components.append({
                        "name": name,
                        "file": str(p.relative_to(root)),
                    })
    return components[:300]


# ─── Incomplete / Stub Detection ──────────────────────────────────────────────

def scan_stubs(root: Path) -> list:
    """Find TODO, FIXME, stubs, placeholders across the codebase."""
    stubs = []
    compiled = [(re.compile(pat, re.IGNORECASE), label) for pat, label in STUB_PATTERNS]

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        parts = set(p.parts)
        if parts & SKIP_DIRS:
            continue
        if p.suffix not in SCAN_EXTENSIONS:
            continue
        content = safe_read(p, max_bytes=200_000)
        lines   = content.splitlines()
        for lineno, line in enumerate(lines, 1):
            for pattern, label in compiled:
                if pattern.search(line):
                    stubs.append({
                        "file":    str(p.relative_to(root)),
                        "line":    lineno,
                        "type":    label,
                        "snippet": line.strip()[:120],
                    })
                    break   # one label per line is enough
    return stubs[:500]


def detect_empty_functions(root: Path) -> list:
    """Find Python functions with only 'pass' or docstring bodies."""
    empties = []
    for p in root.rglob("*.py"):
        parts = set(p.parts)
        if parts & SKIP_DIRS:
            continue
        content = safe_read(p)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                # Body is just a pass or docstring
                is_empty = (
                    len(body) == 1 and isinstance(body[0], ast.Pass)
                ) or (
                    len(body) == 1 and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                )
                if is_empty:
                    empties.append({
                        "file": str(p.relative_to(root)),
                        "function": node.name,
                        "line": node.lineno,
                    })
    return empties[:100]


# ─── Project Classification ────────────────────────────────────────────────────

def classify_project(root: Path, frameworks: list, routes: list,
                     pkg: dict, languages: list) -> str:
    """
    Classify the project domain based on heuristics.
    Returns a domain string for the research phase.
    """
    # Check for strong framework indicators first
    if "wordpress" in frameworks:
        return "wordpress-cms"
    if "electron" in frameworks:
        return "desktop-app"
    if "django" in frameworks or "flask" in frameworks or "fastapi" in frameworks:
        # Check if it's an API-only or full-stack Django
        if any(r["type"] == "page" for r in routes):
            return "python-web-app"
        return "python-api"

    # Check folder names for strong domain signals
    folder_names = {p.name.lower() for p in root.iterdir() if p.is_dir()}
    name_lower   = pkg.get("name", "").lower()

    domains_from_name = {
        "dashboard":  "saas-dashboard",
        "admin":      "admin-portal",
        "shop":       "ecommerce",
        "store":      "ecommerce",
        "blog":       "blog-cms",
        "cms":        "blog-cms",
        "api":        "rest-api",
        "auth":       "auth-service",
        "chat":       "chat-messaging",
        "social":     "social-platform",
        "analytics":  "analytics-platform",
        "crm":        "crm",
        "erp":        "erp",
        "hr":         "hr-platform",
        "finance":    "fintech",
        "payment":    "fintech",
        "health":     "healthtech",
        "medical":    "healthtech",
        "school":     "edtech",
        "learn":      "edtech",
        "game":       "game",
        "music":      "music-app",
        "media":      "media-platform",
        "booking":    "booking-platform",
        "schedule":   "scheduling-app",
        "pool":       "sports-pool",
        "picks":      "sports-pool",
        "commish":    "sports-pool",
        "fantasy":    "fantasy-sports",
        "monitor":    "monitoring-dashboard",
        "ops":        "ops-dashboard",
    }

    all_signals = folder_names | {name_lower} | {w for w in name_lower.split("-")}
    for signal, domain in domains_from_name.items():
        if signal in all_signals:
            return domain

    # Check route paths
    route_paths = " ".join(r["path"] for r in routes).lower()
    for signal, domain in domains_from_name.items():
        if signal in route_paths:
            return domain

    # Fallback by primary language + framework
    top_ext = languages[0]["ext"] if languages else ".js"
    if "next.js" in frameworks:
        return "nextjs-web-app"
    if "react" in frameworks:
        return "react-app"
    if "vue" in frameworks:
        return "vue-app"
    if ".py" == top_ext:
        return "python-app"
    if ".cs" == top_ext:
        return "dotnet-app"
    return "web-app"


# ─── Git / Repo Info ──────────────────────────────────────────────────────────

def get_git_info(root: Path) -> dict:
    """Extract recent git commit info for activity context."""
    info = {}
    try:
        log = subprocess.check_output(
            ["git", "-C", str(root), "log", "--oneline", "-20"],
            stderr=subprocess.DEVNULL, text=True
        )
        info["recent_commits"] = [l.strip() for l in log.strip().splitlines()]
    except Exception:
        info["recent_commits"] = []
    try:
        branches = subprocess.check_output(
            ["git", "-C", str(root), "branch", "-a"],
            stderr=subprocess.DEVNULL, text=True
        )
        info["branches"] = [b.strip().lstrip("* ") for b in branches.splitlines()][:10]
    except Exception:
        info["branches"] = []
    try:
        remote = subprocess.check_output(
            ["git", "-C", str(root), "remote", "-v"],
            stderr=subprocess.DEVNULL, text=True
        )
        info["remote"] = remote.strip().splitlines()[0] if remote.strip() else ""
    except Exception:
        info["remote"] = ""
    return info


# ─── Project Summary Stats ────────────────────────────────────────────────────

def project_stats(root: Path) -> dict:
    """High-level LOC and file counts."""
    total_files = 0
    total_lines = 0
    by_type     = defaultdict(int)
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        parts = set(p.parts)
        if parts & SKIP_DIRS:
            continue
        if p.suffix in SCAN_EXTENSIONS:
            total_files += 1
            lc = file_line_count(p)
            total_lines += lc
            by_type[p.suffix] += lc
    return {
        "total_files": total_files,
        "total_lines": total_lines,
        "lines_by_type": dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:10]),
    }


# ─── Config / Feature File Detection ─────────────────────────────────────────

def detect_feature_flags(root: Path) -> list:
    """Find feature flag patterns in code."""
    flags = []
    patterns = [
        r"FEATURE_(\w+)\s*[=:]\s*(true|false|1|0)",
        r"feature[_\-]flag[s]?[\s\S]{0,20}['\"](\w+)['\"]",
        r"isEnabled\(['\"](\w+)['\"]",
        r"featureFlags\.(\w+)",
        r"flags\.(\w+)",
    ]
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    for fp in root.rglob("*"):
        if not fp.is_file():
            continue
        parts = set(fp.parts)
        if parts & SKIP_DIRS:
            continue
        if fp.suffix not in SCAN_EXTENSIONS:
            continue
        content = safe_read(fp, 100_000)
        for pat in compiled:
            for m in pat.finditer(content):
                name = m.group(1) if m.lastindex else m.group(0)
                if name and len(name) < 60:
                    flags.append({"flag": name, "file": str(fp.relative_to(root))})
    return list({f["flag"]: f for f in flags}.values())[:50]


def detect_env_vars(root: Path) -> list:
    """Extract env var names from .env.example or .env.sample."""
    env_files = [".env.example", ".env.sample", ".env.local.example", ".env.template"]
    vars_found = []
    for ef in env_files:
        ep = root / ef
        if not ep.exists():
            continue
        lines = safe_read(ep).splitlines()
        for line in lines:
            if "=" in line and not line.startswith("#"):
                key = line.split("=")[0].strip()
                if key:
                    vars_found.append(key)
    return vars_found[:80]


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Discover project context for feature enhancement.")
    parser.add_argument("target",             nargs="?", default=".", help="Target directory path")
    parser.add_argument("--forgejo-url",      help="Forgejo repo URL to clone first")
    parser.add_argument("--output",  "-o",   default="-",              help="Output path (- = stdout)")
    parser.add_argument("--clone-dir",        default="/tmp/fe-clone",  help="Where to clone if --forgejo-url given")
    args = parser.parse_args()

    # ── Handle Forgejo clone ─────────────────────────────────────────────────
    if args.forgejo_url:
        print(f"[discover] Cloning {args.forgejo_url} → {args.clone_dir} ...", file=sys.stderr)
        os.makedirs(args.clone_dir, exist_ok=True)
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", args.forgejo_url, args.clone_dir],
                check=True, capture_output=True, text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"[discover] Clone failed: {e.stderr}", file=sys.stderr)
            sys.exit(1)
        root = Path(args.clone_dir)
    else:
        root = Path(args.target).resolve()

    if not root.exists() or not root.is_dir():
        print(f"[discover] ERROR: {root} is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"[discover] Scanning {root} ...", file=sys.stderr)

    # ── Run all discovery phases ─────────────────────────────────────────────
    pkg        = parse_package_json(root)
    py_reqs    = parse_requirements(root)
    py_pkg     = parse_pyproject(root)
    languages  = detect_languages(root)
    frameworks = detect_frameworks(root, pkg)
    databases  = detect_databases(root, pkg)
    auth_tools = detect_auth(root, pkg)
    routes     = detect_routes(root, frameworks)
    components = detect_components(root)
    stubs      = scan_stubs(root)
    empties    = detect_empty_functions(root)
    git_info   = get_git_info(root)
    stats      = project_stats(root)
    flags      = detect_feature_flags(root)
    env_vars   = detect_env_vars(root)
    domain     = classify_project(root, frameworks, routes, pkg, languages)

    # ── Assemble output ──────────────────────────────────────────────────────
    context = {
        "root":          str(root),
        "domain":        domain,
        "project_name":  pkg.get("name") or root.name,
        "project_version": pkg.get("version", ""),
        "languages":     languages,
        "frameworks":    frameworks,
        "databases":     databases,
        "auth_tools":    auth_tools,
        "npm_scripts":   pkg.get("scripts", []),
        "runtime_deps":  (pkg.get("runtime") or []) + (py_reqs or []) + (py_pkg.get("runtime") or []),
        "dev_deps":      pkg.get("dev", []),
        "routes":        routes,
        "components":    components,
        "stubs":         stubs,
        "empty_functions": empties,
        "feature_flags": flags,
        "env_vars":      env_vars,
        "git":           git_info,
        "stats":         stats,
        # Summary counts for quick reference
        "summary": {
            "total_routes":       len(routes),
            "total_components":   len(components),
            "total_stubs":        len(stubs),
            "total_empty_fns":    len(empties),
            "total_feature_flags": len(flags),
        },
    }

    output_str = json.dumps(context, indent=2)

    if args.output == "-":
        print(output_str)
    else:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output_str, encoding="utf-8")
        print(f"[discover] Context written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
