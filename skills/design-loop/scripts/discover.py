#!/usr/bin/env python3
"""Scan a project directory and emit a project-context.json to stdout.

Detects:
  - Language/runtime stacks (node, python, rust, go, ruby, php, dart, dotnet, swift, kotlin/java)
  - UI frameworks and style systems
  - Multiple UI surfaces in a monorepo (emits a ui_surfaces list when >1)
  - Project type (heuristic over README/package metadata/docs)
  - Existing screenshots, component dirs, style files

Usage:
    discover.py <target_path> [--surface <relative_subdir>]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STACK_MARKERS = {
    "package.json":     "node",
    "pyproject.toml":   "python",
    "requirements.txt": "python",
    "Cargo.toml":       "rust",
    "go.mod":           "go",
    "Gemfile":          "ruby",
    "composer.json":    "php",
    "pubspec.yaml":     "dart",
    "build.gradle":     "kotlin/java",
    "Package.swift":    "swift",
}

SUFFIX_MARKERS = {
    ".csproj": "dotnet",
    ".fsproj": "dotnet",
    ".sln":    "dotnet",
}

UI_FRAMEWORK_HINTS = {
    "next":                "nextjs",
    "nuxt":                "nuxt",
    "react":               "react",
    "vue":                 "vue",
    "svelte":              "svelte",
    "solid":               "solid",
    "remix":               "remix",
    "astro":               "astro",
    "tailwindcss":         "tailwind",
    "@shadcn":             "shadcn",
    "shadcn-ui":           "shadcn",
    "styled-components":   "styled-components",
    "emotion":             "emotion",
    "chakra":              "chakra",
    "mantine":             "mantine",
    "@mui":                "mui",
    "antd":                "antd",
    "radix-ui":            "radix",
    "framer-motion":       "framer-motion",
    "@headlessui":         "headlessui",
    "streamlit":           "streamlit",
    "gradio":              "gradio",
}

# Python UI frameworks — detected via pyproject/requirements rather than package.json
PY_UI_HINTS = {
    "streamlit": "streamlit",
    "gradio":    "gradio",
    "dash":      "dash",
    "flask":     "flask-html",
    "django":    "django-html",
}

PROJECT_TYPE_HEURISTICS = [
    ("saas-dashboard", ["dashboard", "admin", "console", "analytics", "metrics", "kpi", "saas"]),
    ("marketing",      ["landing", "marketing", "hero", "cta", "waitlist", "pricing page"]),
    ("dev-tool",       ["cli", "sdk", "devtool", "terminal", "editor", "compiler", "linter", "debugger"]),
    ("internal-ops",   ["internal", "back-office", "back office", "crm", "erp", "ops tool", "admin panel"]),
    ("ecommerce",      ["shop", "cart", "checkout", "product", "store", "sku", "inventory"]),
    ("creative",       ["music", "video", "audio", "canvas", "design tool", "studio", "daw", "synth"]),
    ("game",           ["gameplay", "unity", "godot", "game engine", "player hud", "levels"]),
    ("docs",           ["documentation", "docs site", "wiki", "handbook", "changelog", "knowledge base"]),
]

IGNORE = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", "target",
          "venv", ".venv", "__pycache__", ".cache", "coverage", ".turbo", ".svelte-kit"}

# Paths to the versioned data libraries, relative to this script
SKILL_ROOT = Path(__file__).resolve().parent.parent
REFERENCES_PATH = SKILL_ROOT / "data" / "references.json"
DIMENSIONS_PATH = SKILL_ROOT / "data" / "dimensions.json"


def peek_data_version():
    """Return the combined data library version string, or 'unknown' if unreadable."""
    versions = []
    for path in (REFERENCES_PATH, DIMENSIONS_PATH):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            versions.append(data.get("version", "unversioned") if isinstance(data, dict) else "unversioned")
        except Exception:
            versions.append("unreadable")
    if len(set(versions)) == 1:
        return versions[0]
    return "/".join(versions)

# Caps so huge repos don't blow up the walker
MAX_DOC_BYTES = 8000
MAX_WALK_ENTRIES = 20000

# Monorepo markers — dirs whose children are treated as candidate UI surfaces
MONOREPO_MARKER_DIRS = {"apps", "packages", "services", "sites"}


def walk(root, max_depth=4):
    root = Path(root)
    count = 0
    for p in root.rglob("*"):
        if count > MAX_WALK_ENTRIES:
            break
        count += 1
        if any(part in IGNORE for part in p.parts):
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if len(rel.parts) > max_depth:
            continue
        yield p


def detect_stack(root):
    found = {}
    root = Path(root)
    for p in walk(root, max_depth=2):
        if not p.is_file():
            continue
        name = p.name
        if name in STACK_MARKERS:
            stack = STACK_MARKERS[name]
            found.setdefault(stack, []).append(str(p.relative_to(root)).replace("\\", "/"))
        elif p.suffix in SUFFIX_MARKERS:
            stack = SUFFIX_MARKERS[p.suffix]
            found.setdefault(stack, []).append(str(p.relative_to(root)).replace("\\", "/"))
    return found


def _scan_package_json(pkg_path):
    """Return set of UI framework names from a package.json's deps."""
    hits = set()
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return hits
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    for hint, name in UI_FRAMEWORK_HINTS.items():
        if any(hint in dep.lower() for dep in deps):
            hits.add(name)
    return hits


def _scan_python_deps(root):
    """Return set of UI framework names from pyproject.toml / requirements.txt."""
    hits = set()
    text = ""
    for candidate in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"):
        p = root / candidate
        if p.exists() and p.is_file():
            text += p.read_text(encoding="utf-8", errors="ignore").lower() + "\n"
    for hint, name in PY_UI_HINTS.items():
        if hint in text:
            hits.add(name)
    return hits


def _scan_tailwind_config(root):
    hits = set()
    for cfg in ("tailwind.config.js", "tailwind.config.ts",
                "tailwind.config.cjs", "tailwind.config.mjs"):
        if (root / cfg).exists():
            hits.add("tailwind")
            break
    return hits


def detect_ui_framework(root):
    root = Path(root)
    hits = set()
    pkg = root / "package.json"
    if pkg.exists():
        hits |= _scan_package_json(pkg)
    hits |= _scan_python_deps(root)
    hits |= _scan_tailwind_config(root)
    # HTML-only site fallback: if there's an index.html at root with no deps
    if not hits and (root / "index.html").exists():
        hits.add("plain-html")
    return sorted(hits)


def detect_ui_surfaces(root):
    """Find UI surfaces in a monorepo. Returns a list of relative subdir paths.

    A surface is any subdirectory under apps/|packages/|services/|sites/ that
    has its own UI-framework signature (package.json with UI deps, or a
    tailwind config, or a Python UI framework).
    """
    root = Path(root)
    surfaces = []
    for marker in MONOREPO_MARKER_DIRS:
        mdir = root / marker
        if not mdir.is_dir():
            continue
        for sub in sorted(mdir.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            sub_hits = set()
            if (sub / "package.json").exists():
                sub_hits |= _scan_package_json(sub / "package.json")
            sub_hits |= _scan_python_deps(sub)
            sub_hits |= _scan_tailwind_config(sub)
            if not sub_hits and (sub / "index.html").exists():
                sub_hits.add("plain-html")
            if sub_hits:
                rel = str(sub.relative_to(root)).replace("\\", "/")
                surfaces.append({
                    "path": rel,
                    "ui_framework": sorted(sub_hits),
                })
    return surfaces


def detect_style_system(artifacts, ui_framework):
    """Derive a concise style-system string from detected artifacts and frameworks."""
    style_files = artifacts.get("style_files", [])
    parts = []
    if "tailwind" in ui_framework:
        parts.append("Tailwind")
    if "shadcn" in ui_framework:
        parts.append("shadcn/ui")
    if "styled-components" in ui_framework:
        parts.append("styled-components")
    if "emotion" in ui_framework:
        parts.append("Emotion")
    if "chakra" in ui_framework:
        parts.append("Chakra")
    if "mui" in ui_framework:
        parts.append("MUI")
    if "mantine" in ui_framework:
        parts.append("Mantine")
    if "radix" in ui_framework:
        parts.append("Radix primitives")
    if "streamlit" in ui_framework:
        parts.append("Streamlit default theme")
    if "gradio" in ui_framework:
        parts.append("Gradio default theme")
    if any("tokens" in f.lower() for f in style_files):
        parts.append("custom design tokens")
    if any("theme" in f.lower() for f in style_files):
        parts.append("theme file")
    if not parts:
        if style_files:
            parts.append("plain CSS")
        else:
            parts.append("undetected — inspect before proposing")
    return ", ".join(parts)


def extract_text_corpus(root):
    """Read README + package description + any top-level docs for domain signals."""
    root = Path(root)
    corpus = []
    for candidate in ("README.md", "README.rst", "README.txt", "README"):
        p = root / candidate
        if p.exists() and p.is_file():
            corpus.append(p.read_text(encoding="utf-8", errors="ignore")[:MAX_DOC_BYTES])
            break
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
            for key in ("name", "description", "keywords"):
                val = data.get(key)
                if val:
                    corpus.append(str(val))
        except Exception:
            pass
    pyproj = root / "pyproject.toml"
    if pyproj.exists():
        corpus.append(pyproj.read_text(encoding="utf-8", errors="ignore")[:MAX_DOC_BYTES])
    docs = root / "docs"
    if docs.exists() and docs.is_dir():
        for md in sorted(docs.glob("*.md"))[:5]:
            corpus.append(md.read_text(encoding="utf-8", errors="ignore")[:2000])
    return "\n".join(corpus).lower()


def classify_project_type(corpus, ui_framework):
    scores = {t: 0 for t, _ in PROJECT_TYPE_HEURISTICS}
    for ptype, signals in PROJECT_TYPE_HEURISTICS:
        for s in signals:
            scores[ptype] += corpus.count(s)
    top = max(scores.values()) if scores else 0
    if top == 0:
        return "saas-dashboard" if ui_framework else "unknown"
    for ptype, _ in PROJECT_TYPE_HEURISTICS:
        if scores[ptype] == top:
            return ptype
    return "unknown"


def find_ui_artifacts(root):
    root = Path(root)
    artifacts = {"screenshots": [], "component_dirs": [], "style_files": []}
    seen_dirs = set()
    for p in walk(root):
        try:
            rel = str(p.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
        rel_lower = rel.lower()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            try:
                if p.stat().st_size > 10_000 and any(
                    k in rel_lower for k in ("screenshot", "mockup", "design", "preview", "hero")
                ):
                    artifacts["screenshots"].append(rel)
            except OSError:
                pass
        if p.is_dir() and p.name.lower() in {"components", "ui", "widgets"} and rel not in seen_dirs:
            artifacts["component_dirs"].append(rel)
            seen_dirs.add(rel)
        if p.is_file() and p.name in {
            "tailwind.config.js", "tailwind.config.ts", "tailwind.config.cjs", "tailwind.config.mjs",
            "theme.ts", "theme.js", "tokens.css", "tokens.ts", "globals.css", "app.css", "index.css",
        }:
            artifacts["style_files"].append(rel)
    for k in artifacts:
        artifacts[k] = artifacts[k][:20]
    return artifacts


def collect_domain_hints(corpus):
    hits = []
    for _, signals in PROJECT_TYPE_HEURISTICS:
        for s in signals:
            if s in corpus and s not in hits:
                hits.append(s)
    return hits[:10]


def build_context(target, surface=None):
    # If a surface was specified, scope the analysis to that subdirectory.
    analysis_root = target / surface if surface else target
    if not analysis_root.exists() or not analysis_root.is_dir():
        print(f"Surface not found: {analysis_root}", file=sys.stderr)
        sys.exit(2)

    corpus = extract_text_corpus(analysis_root)
    ui = detect_ui_framework(analysis_root)
    artifacts = find_ui_artifacts(analysis_root)

    # ui_surfaces is always computed from the TOP-level target, not the scoped
    # analysis root — the caller needs to know about siblings.
    ui_surfaces = detect_ui_surfaces(target) if surface is None else []

    context = {
        "schema_version": "1.0",
        "data_version":   peek_data_version(),
        "generated_at":   datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_path":   str(target),
        "project_name":   target.name,
        "analysis_root":  str(analysis_root),
        "surface":        surface,
        "ui_surfaces":    ui_surfaces,
        "stack":          detect_stack(analysis_root),
        "ui_framework":   ui,
        "style_system":   detect_style_system(artifacts, ui),
        "project_type":   classify_project_type(corpus, ui),
        "artifacts":      artifacts,
        "domain_hints":   collect_domain_hints(corpus),
    }

    # Emit a hint when we found multiple surfaces AND the caller didn't pick one.
    if ui_surfaces and len(ui_surfaces) > 1 and surface is None:
        context["_monorepo_warning"] = (
            f"Detected {len(ui_surfaces)} UI surfaces. "
            "Pick one with --surface <path> on generate_prompt.py, "
            f"or re-run discover.py with --surface. Options: "
            + ", ".join(s["path"] for s in ui_surfaces)
        )

    return context


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target_path")
    ap.add_argument("--surface", default=None,
                    help="Relative subdirectory to scope analysis to (e.g. apps/admin)")
    args = ap.parse_args()

    target = Path(args.target_path).resolve()
    if not target.exists() or not target.is_dir():
        print(f"Target not a directory: {target}", file=sys.stderr)
        sys.exit(2)

    context = build_context(target, surface=args.surface)
    print(json.dumps(context, indent=2))


if __name__ == "__main__":
    main()
