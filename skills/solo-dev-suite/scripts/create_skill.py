#!/usr/bin/env python3
"""
create_skill.py -- Scaffold a new child skill for the Solo Dev Suite.

Creates the complete directory structure, registers the skill in
children.json and marketplace.json, and generates starter files
following all suite conventions.

Commands:
    new  <name> --description <desc> --phases <phase1,phase2> [--author <name>]

Exit codes:
    0  success
    1  skill already exists
    2  invalid arguments
    3  suite install broken

Design notes:
  * No external deps. Pure stdlib.
  * Generates files that pass the CI validation workflow.
  * Does NOT overwrite existing files.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_DIR = SCRIPT_DIR.parent                      # skills/solo-dev-suite
SKILLS_ROOT = SUITE_DIR.parent                     # skills/
REPO_ROOT = SKILLS_ROOT.parent                     # repo root
CHILDREN_PATH = SUITE_DIR / "data" / "children.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

VALID_PHASES = ("idea", "scope", "architecture", "build", "ship", "grow", "sustain", "any")


def _err(msg: str) -> None:
    print(f"[create_skill] {msg}", file=sys.stderr)


def _validate_name(name: str) -> bool:
    """Skill name must be kebab-case."""
    return bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name))


def _write_file(path: Path, content: str) -> None:
    """Write a file, creating parent dirs as needed. Does NOT overwrite."""
    if path.exists():
        _err(f"Skipping (already exists): {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  Created: {path.relative_to(REPO_ROOT)}")


def _generate_skill_md(name: str, description: str, phases: List[str]) -> str:
    """Generate the SKILL.md content."""
    title = name.replace("-", " ").title()
    phase_list = ", ".join(phases)
    return f"""---
name: {name}
version: 1.0.0
description: {description}
---

# {title}

{description}

## When to use this skill

- (Describe the primary use cases)

## When NOT to use this skill

- **No profile exists** -- run the orchestrator first.
- (Add other exclusions)

## Commands

### 1. init

Initialize the skill for a project:

```bash
python "<SKILL_DIR>/scripts/{name.replace('-', '_')}_tool.py" init <slug>
```

### 2. show

Display current state:

```bash
python "<SKILL_DIR>/scripts/{name.replace('-', '_')}_tool.py" show <slug>
```

### 3. render

Generate Markdown output:

```bash
python "<SKILL_DIR>/scripts/{name.replace('-', '_')}_tool.py" render <slug>
```

## Files

```
{name}/
├── SKILL.md                          # this file
├── .claude-plugin/
│   └── plugin.json                   # plugin metadata
└── scripts/
    └── {name.replace('-', '_')}_tool.py   # main tool script
```

## Phases

Active in: {phase_list}
"""


def _generate_tool_py(name: str, description: str) -> str:
    """Generate the starter tool script."""
    module = name.replace("-", "_")
    return f'''#!/usr/bin/env python3
"""
{module}_tool.py -- {description}

Commands:
    init    <slug>           # initialize for a project
    show    <slug> [--json]  # display current state
    render  <slug>           # generate Markdown output

Exit codes:
    0  success
    1  slug not found
    2  suite install broken
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
SUITE_DIR = SKILL_DIR.parent / "solo-dev-suite"
PROFILES_DIR = SUITE_DIR / "profiles"


def _err(msg: str) -> None:
    print(f"[{module}] {{msg}}", file=sys.stderr)


def _sidecar_path(slug: str) -> Path:
    return PROFILES_DIR / f"{{slug}}.{module.replace('_', '-')}.json"


def _load_profile(slug: str) -> Optional[Dict[str, Any]]:
    path = PROFILES_DIR / f"{{slug}}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def cmd_init(args: argparse.Namespace) -> int:
    profile = _load_profile(args.slug)
    if profile is None:
        _err(f"No profile for slug '{{args.slug}}'.")
        return 1
    # TODO: implement initialization logic
    print(f"Initialized {module} for {{args.slug}}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    sidecar = _sidecar_path(args.slug)
    if not sidecar.exists():
        _err(f"No {module} data for '{{args.slug}}'. Run init first.")
        return 1
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"\\n  {{args.slug}} — {module}\\n")
        print(json.dumps(data, indent=2))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    # TODO: implement Markdown rendering
    _err("render not yet implemented")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="{module}", description="{description}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize for a project.")
    p_init.add_argument("slug", help="Project slug.")
    p_init.set_defaults(func=cmd_init)

    p_show = sub.add_parser("show", help="Display current state.")
    p_show.add_argument("slug", help="Project slug.")
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_render = sub.add_parser("render", help="Generate Markdown output.")
    p_render.add_argument("slug", help="Project slug.")
    p_render.set_defaults(func=cmd_render)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
'''


def _generate_plugin_json(name: str, description: str, author: str) -> str:
    """Generate plugin.json."""
    return json.dumps({
        "name": name,
        "version": "1.0.0",
        "description": description,
        "author": {"name": author},
        "license": "MIT",
        "keywords": [name]
    }, indent=2) + "\n"


def _register_children(name: str, description: str, phases: List[str]) -> None:
    """Add entry to children.json."""
    if not CHILDREN_PATH.exists():
        _err(f"children.json not found at {CHILDREN_PATH}")
        return

    data = json.loads(CHILDREN_PATH.read_text(encoding="utf-8"))
    children = data.get("children", [])

    # Check for duplicate
    if any(c["name"] == name for c in children):
        _err(f"'{name}' already exists in children.json — skipping")
        return

    module = name.replace("-", "_")
    entry = {
        "name": name,
        "version": "1.0.0",
        "status": "active",
        "phases": phases,
        "depends_on": [],
        "enhances": [],
        "description": description,
        "triggers": [
            f"run {name}",
            f"{name.replace('-', ' ')}"
        ],
        "output_location": f"profiles/<slug>.{name}.json"
    }

    # Insert alphabetically
    children.append(entry)
    children.sort(key=lambda c: c["name"])
    data["children"] = children

    tmp = CHILDREN_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(CHILDREN_PATH)
    print(f"  Registered in children.json")


def _register_marketplace(name: str, description: str, author: str) -> None:
    """Add entry to marketplace.json."""
    if not MARKETPLACE_PATH.exists():
        _err(f"marketplace.json not found — skipping")
        return

    data = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
    plugins = data.get("plugins", [])

    if any(p["name"] == name for p in plugins):
        _err(f"'{name}' already in marketplace.json — skipping")
        return

    plugins.append({
        "name": name,
        "description": description,
        "version": "1.0.0",
        "source": f"./skills/{name}",
        "author": {"name": author}
    })
    data["plugins"] = plugins

    tmp = MARKETPLACE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(MARKETPLACE_PATH)
    print(f"  Registered in marketplace.json")


def cmd_new(args: argparse.Namespace) -> int:
    """Scaffold a new child skill."""
    name = args.name
    description = args.description
    phases = [p.strip() for p in args.phases.split(",")]
    author = args.author

    if not _validate_name(name):
        _err(f"Invalid skill name '{name}'. Must be kebab-case (lowercase, hyphens only).")
        return 2

    for p in phases:
        if p not in VALID_PHASES:
            _err(f"Invalid phase '{p}'. Must be one of: {', '.join(VALID_PHASES)}")
            return 2

    skill_dir = SKILLS_ROOT / name
    if skill_dir.exists():
        _err(f"Directory already exists: {skill_dir}")
        return 1

    print(f"\n  Creating skill: {name}\n")

    module = name.replace("-", "_")

    # Create files
    _write_file(skill_dir / "SKILL.md", _generate_skill_md(name, description, phases))
    _write_file(skill_dir / ".claude-plugin" / "plugin.json",
                _generate_plugin_json(name, description, author))
    _write_file(skill_dir / "scripts" / f"{module}_tool.py",
                _generate_tool_py(name, description))

    # Register in children.json and marketplace.json
    _register_children(name, description, phases)
    _register_marketplace(name, description, author)

    print(f"\n  Skill '{name}' scaffolded successfully.")
    print(f"  Next steps:")
    print(f"    1. Edit skills/{name}/SKILL.md — fill in the playbook")
    print(f"    2. Edit skills/{name}/scripts/{module}_tool.py — implement the logic")
    print(f"    3. Update children.json — add triggers, depends_on, enhances")
    print(f"    4. Test: python skills/{name}/scripts/{module}_tool.py --help\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="create_skill",
        description="Scaffold a new child skill for the Solo Dev Suite.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Create a new skill.")
    p_new.add_argument("name", help="Skill name (kebab-case, e.g. 'accessibility-checker').")
    p_new.add_argument("--description", required=True, help="One-line description.")
    p_new.add_argument("--phases", required=True, help="Comma-separated phases (e.g. 'build,ship').")
    p_new.add_argument("--author", default="Frank Robinson", help="Author name.")
    p_new.set_defaults(func=cmd_new)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
