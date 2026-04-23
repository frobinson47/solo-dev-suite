#!/usr/bin/env python3
"""Validate a generated LOOP_PROMPT.md against the design-loop output contract.

Asserts that every required section is present and non-empty. Exits 0 on success,
1 on any failure. Prints a checklist to stderr showing which checks passed.

The checks are intentionally structural (section headers, keywords) rather than
semantic — the goal is to catch template regressions and empty placeholders,
not to grade the design direction.

Usage:
    validate_prompt.py <path_to_LOOP_PROMPT.md>
    validate_prompt.py <path_to_LOOP_PROMPT.md> --quiet   # only prints on failure
"""
import argparse
import re
import sys
from pathlib import Path


# Each check is (id, description, callable(text) -> (bool, str))
# Returning (False, reason) means the check failed.


def check_mission(text):
    m = re.search(r"^MISSION:\s*Evolve\s+\*\*(.+?)\*\*\s*\((.+?)\)", text, re.MULTILINE)
    if not m:
        return False, "no `MISSION: Evolve **<name>** (<type>)` line found"
    name, ptype = m.group(1).strip(), m.group(2).strip()
    if not name or name == "this project":
        return False, f"mission project name looks unfilled ({name!r})"
    if not ptype:
        return False, "mission project type is empty"
    return True, f"name={name!r}, type={ptype!r}"


def check_references(text):
    section = _extract_section(text, "Reference aesthetic")
    if section is None:
        return False, "missing `## Reference aesthetic` section"
    refs = [line[2:].strip() for line in section.splitlines() if line.startswith("- ")]
    if len(refs) != 5:
        return False, f"expected exactly 5 references, found {len(refs)}: {refs}"
    return True, f"5 refs: {refs}"


def check_per_loop_deliverables(text):
    section = _extract_section(text, "Per-loop deliverables")
    if section is None:
        return False, "missing `## Per-loop deliverables` section"
    # Expect a numbered list of 5 items
    items = re.findall(r"^\s*(\d+)\.\s+(.+)$", section, re.MULTILINE)
    if len(items) < 5:
        return False, f"expected at least 5 numbered deliverables, found {len(items)}"
    return True, f"{len(items)} numbered deliverables"


def check_dimensions(text):
    section = _extract_section(text, "Exploration dimensions")
    if section is None:
        return False, "missing `## Exploration dimensions` section"
    dims = [line[2:].strip() for line in section.splitlines() if line.startswith("- ")]
    if len(dims) < 5:
        return False, f"expected >=5 dimensions, found {len(dims)}"
    # Unfilled placeholder check
    joined = "\n".join(dims)
    if "{{" in joined or "}}" in joined:
        return False, f"unfilled placeholder in dimensions: {joined!r}"
    return True, f"{len(dims)} dimensions"


def check_stack_constraints(text):
    section = _extract_section(text, "Detected stack constraints")
    if section is None:
        return False, "missing `## Detected stack constraints` section"
    required_labels = ("Framework:", "Style system:", "Existing components at:")
    missing = [lbl for lbl in required_labels if lbl not in section]
    if missing:
        return False, f"missing labels in stack constraints: {missing}"
    return True, "framework, style system, and component dirs all labeled"


def check_convergence_clause(text):
    section = _extract_section(text, "Iteration rules")
    if section is None:
        return False, "missing `## Iteration rules` section (convergence lives here)"
    must_contain = ("manifesto.md", "Hero mockup")
    missing = [s for s in must_contain if s not in section]
    if missing:
        return False, f"convergence clause missing: {missing}"
    # Also verify hero screen is filled in (not a literal {{hero_screen}})
    if "{{hero_screen}}" in section:
        return False, "hero screen placeholder never replaced"
    return True, "manifesto.md + hero mockup both named"


def check_version_tag(text):
    m = re.search(r"design-loop version:\s*(\S+)", text)
    if not m:
        return False, "no `design-loop version: <x>` header comment found"
    v = m.group(1)
    if v in ("{{data_version}}", "unknown", "unreadable"):
        return False, f"version tag unfilled or unreadable: {v!r}"
    return True, f"version={v!r}"


def check_no_unfilled_placeholders(text):
    """Catch-all for any {{...}} that escaped templating."""
    leftovers = re.findall(r"\{\{[^}]+\}\}", text)
    if leftovers:
        return False, f"unfilled placeholders: {sorted(set(leftovers))}"
    return True, "no leftover {{placeholders}}"


CHECKS = [
    ("mission",           "Mission statement with project name + type", check_mission),
    ("references",        "Reference set of exactly 5 products",        check_references),
    ("deliverables",      "Per-loop deliverables (>=5 artifact types)", check_per_loop_deliverables),
    ("dimensions",        "Exploration dimensions (>=5, scoped)",       check_dimensions),
    ("stack_constraints", "Detected stack constraints (all 3 labels)",  check_stack_constraints),
    ("convergence",       "Loop-N convergence clause (manifesto+hero)", check_convergence_clause),
    ("version_tag",       "Data library version tag in header",         check_version_tag),
    ("no_placeholders",   "No unfilled {{placeholders}} anywhere",      check_no_unfilled_placeholders),
]


def _extract_section(text, heading):
    """Return the body of a `## <heading>` section up to the next `## ` (or EOF).

    Matches on heading prefix (case-sensitive) so parenthetical suffixes in
    the heading (e.g. "Reference aesthetic (study, don't copy)") still match
    when the check asks for "Reference aesthetic".

    Splits on lines that start with `## ` — more reliable than a single regex
    with lookaheads, which misbehaves near the last section in the document.
    """
    parts = re.split(r"(?m)^##\s+", text)
    for part in parts[1:]:  # skip preamble
        lines = part.split("\n", 1)
        if not lines:
            continue
        section_heading = lines[0].strip()
        body = lines[1] if len(lines) > 1 else ""
        # Prefix match: "Reference aesthetic" matches "Reference aesthetic (study, don't copy)"
        if section_heading == heading or section_heading.startswith(heading + " "):
            return body
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("prompt_path")
    ap.add_argument("--quiet", "-q", action="store_true",
                    help="Suppress per-check output on success; only print on failure")
    args = ap.parse_args()

    path = Path(args.prompt_path)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(2)

    text = path.read_text(encoding="utf-8")

    results = []
    for cid, desc, fn in CHECKS:
        try:
            ok, detail = fn(text)
        except Exception as exc:
            ok, detail = False, f"check raised {type(exc).__name__}: {exc}"
        results.append((cid, desc, ok, detail))

    failed = [r for r in results if not r[2]]

    if failed or not args.quiet:
        print(f"Validating: {path}", file=sys.stderr)
        for cid, desc, ok, detail in results:
            marker = "PASS" if ok else "FAIL"
            print(f"  [{marker}] {cid:20s} {desc}", file=sys.stderr)
            if not ok or not args.quiet:
                print(f"           -> {detail}", file=sys.stderr)

    if failed:
        print(f"\n{len(failed)} of {len(results)} checks failed.", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(f"\nAll {len(results)} checks passed.", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
