#!/usr/bin/env python3
"""Fill the design-loop prompt template from a context.json + versioned data libraries.

Usage:
    generate_prompt.py <context.json> [--type TYPE] [--refs a,b,c] [--surface path]
                                      [--loops N] [--duration 10m] [--hero SCREEN]
                                      [--runner /loop] [--min-viewport 1280x800]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
TEMPLATE_PATH = SKILL_ROOT / "templates" / "loop-prompt.md.tmpl"
REFERENCES_PATH = SKILL_ROOT / "data" / "references.json"
DIMENSIONS_PATH = SKILL_ROOT / "data" / "dimensions.json"

DEFAULT_HERO_BY_TYPE = {
    "saas-dashboard": "the primary dashboard / overview screen",
    "marketing":      "the landing page hero + first two sections",
    "dev-tool":       "the main workspace or primary command surface",
    "internal-ops":   "the primary table/list view with filters",
    "ecommerce":      "the product detail page",
    "creative":       "the main canvas / editor workspace",
    "game":           "the main menu + one in-game HUD moment",
    "docs":           "a representative content page with sidebar + TOC",
    "unknown":        "the primary screen users hit first",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_library(path, label):
    """Load a versioned data library. Accepts both old flat shape and new envelope."""
    data = load_json(path)
    if isinstance(data, dict) and "project_types" in data and "version" in data:
        return data["version"], data["project_types"]
    # Backwards compat: flat shape with no version
    print(f"WARN: {label} at {path} has no version envelope — treating as unversioned. "
          f"Migrate to the new schema (see data/README.md).", file=sys.stderr)
    return "unversioned", data


def format_references(refs):
    return "\n".join(f"- {r}" for r in refs)


def format_dimensions(dims):
    return "\n".join(f"- {d}" for d in dims)


def format_component_dirs(dirs):
    if not dirs:
        return "_none detected — propose a structure_"
    return ", ".join(f"`{d}`" for d in dirs[:6])


def format_ui_framework(ui):
    if not ui:
        return "_undetected — confirm with the user before proposing framework-specific code_"
    return ", ".join(ui)


def format_domain_hints(hints):
    if not hints:
        return ""
    return "- **Domain signals picked up from repo:** " + ", ".join(f"`{h}`" for h in hints)


def format_artifact_note(artifacts):
    shots = artifacts.get("screenshots", [])
    comps = artifacts.get("component_dirs", [])
    parts = []
    if shots:
        parts.append(
            f"Existing screenshots/mockups at {', '.join(shots[:3])} — study them before proposing changes."
        )
    if comps:
        parts.append(
            f"Existing component directories at {', '.join(comps[:3])} — respect the structure or deliberately rethink it."
        )
    if not parts:
        parts.append(
            "No existing screenshots or component directories were detected — you'll be starting from the current code."
        )
    return " ".join(parts)


def check_version_drift(ctx, current_version):
    """Warn if the context.json was generated against an older data library version."""
    ctx_version = ctx.get("data_version")  # May not exist on old context.jsons
    if ctx_version is None:
        return
    if ctx_version != current_version:
        print(
            f"WARN: context.json was generated against data library version "
            f"{ctx_version!r} but current is {current_version!r}. "
            f"Re-run discover.py to refresh.",
            file=sys.stderr,
        )


def check_monorepo_unpicked(ctx):
    """Fail hard if the context indicates multiple surfaces and none was picked."""
    if ctx.get("_monorepo_warning") and not ctx.get("surface"):
        print(
            "ERROR: " + ctx["_monorepo_warning"],
            file=sys.stderr,
        )
        sys.exit(3)


def normalize_refs(refs, ptype):
    """Ensure exactly 5 refs. Pad with Linear/Vercel/Stripe if short; trim if long."""
    PAD = ["Linear", "Vercel", "Stripe", "Raycast", "Apple"]
    refs = list(refs)
    if len(refs) > 5:
        print(f"WARN: --refs had {len(refs)} entries; trimming to 5.", file=sys.stderr)
        return refs[:5]
    if len(refs) < 5:
        needed = 5 - len(refs)
        filler = [p for p in PAD if p not in refs][:needed]
        print(f"WARN: --refs had {len(refs)} entries; padding with {filler}.", file=sys.stderr)
        return refs + filler
    return refs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("context_json")
    ap.add_argument("--type", dest="type_override", default=None,
                    help="Override detected project type")
    ap.add_argument("--refs", dest="refs_override", default=None,
                    help="Comma-separated reference list to override auto-pick")
    ap.add_argument("--surface", dest="surface", default=None,
                    help="UI surface path in a monorepo (e.g. apps/admin)")
    ap.add_argument("--loops", dest="loops", type=int, default=6)
    ap.add_argument("--duration", dest="duration", default="10m")
    ap.add_argument("--hero", dest="hero_override", default=None)
    ap.add_argument("--runner", dest="runner", default="/loop",
                    help="Runner invocation embedded in the handoff (default /loop)")
    ap.add_argument("--min-viewport", dest="min_viewport", default="1280x800")
    args = ap.parse_args()

    ctx = load_json(args.context_json)

    # --surface on this script means: tell the user they need to re-run discover with it.
    # We can't retroactively rescope a context.json here.
    if args.surface and ctx.get("surface") != args.surface:
        print(
            f"ERROR: --surface={args.surface} passed to generate_prompt.py, but "
            f"context.json was generated with surface={ctx.get('surface')!r}. "
            f"Re-run: discover.py <target> --surface {args.surface}",
            file=sys.stderr,
        )
        sys.exit(3)

    check_monorepo_unpicked(ctx)

    refs_version, references_lib = load_library(REFERENCES_PATH, "references.json")
    dims_version, dimensions_lib = load_library(DIMENSIONS_PATH, "dimensions.json")
    current_version = refs_version if refs_version == dims_version else f"{refs_version}/{dims_version}"
    check_version_drift(ctx, current_version)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    ptype = args.type_override or ctx.get("project_type") or "unknown"
    if ptype not in references_lib:
        print(f"WARN: unknown project type '{ptype}', falling back to 'unknown'", file=sys.stderr)
        ptype = "unknown"

    if args.refs_override:
        refs = [r.strip() for r in args.refs_override.split(",") if r.strip()]
        refs = normalize_refs(refs, ptype)
    else:
        refs = references_lib.get(ptype, references_lib["unknown"])

    dims = dimensions_lib.get(ptype, dimensions_lib["unknown"])
    hero = args.hero_override or DEFAULT_HERO_BY_TYPE.get(ptype, DEFAULT_HERO_BY_TYPE["unknown"])

    replacements = {
        "{{project_name}}":                ctx.get("project_name", "this project"),
        "{{project_type}}":                ptype,
        "{{artifact_note}}":               format_artifact_note(ctx.get("artifacts", {})),
        "{{references}}":                  format_references(refs),
        "{{dimensions_for_project_type}}": format_dimensions(dims),
        "{{ui_framework}}":                format_ui_framework(ctx.get("ui_framework", [])),
        "{{style_system}}":                ctx.get("style_system") or "_undetected_",
        "{{component_dirs}}":              format_component_dirs(ctx.get("artifacts", {}).get("component_dirs", [])),
        "{{domain_hints_block}}":          format_domain_hints(ctx.get("domain_hints", [])),
        "{{min_viewport}}":                args.min_viewport,
        "{{loop_count}}":                  str(args.loops),
        "{{duration}}":                    args.duration,
        "{{hero_screen}}":                 hero,
        "{{runner}}":                      args.runner,
        "{{data_version}}":                current_version,
        "{{generated_at}}":                datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    out = template
    for k, v in replacements.items():
        out = out.replace(k, v)

    sys.stdout.buffer.write(out.encode("utf-8"))


if __name__ == "__main__":
    main()
