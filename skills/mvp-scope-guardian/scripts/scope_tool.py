#!/usr/bin/env python3
"""
scope_tool.py -- The workhorse for the mvp-scope-guardian skill.

Owns all reads and writes of the per-project sidecar scope file
(solo-dev-suite/profiles/<slug>.scope.json) and the rendered Markdown
docs (MVP_SCOPE.md + MVP_PARKING_LOT.md).

Commands:
    lock     <slug> --from-stdin          # Initial lock from JSON on stdin
    show     <slug> [--json]              # Display current locked scope
    check    <slug> --feature <name> [--description <desc>]
                                          # Scope creep verdict against locked scope
    rescope  <slug> --from-stdin          # Apply patch + append history entry
    render   <slug> [--output-dir <dir>]  # Re-generate the Markdown docs
    delete   <slug> [--yes]               # Remove sidecar + rendered docs

The sidecar is the source of truth. Markdown docs are generated artifacts
and can be re-rendered at any time from the sidecar JSON.

Design notes:
  * Validation is done against templates/scope.schema.json on every write.
  * IDs (LB01, PL01, PK01, WB01) are auto-assigned on write -- callers don't
    manage them. This prevents ID collisions and drift.
  * Scope creep "check" uses simple string matching (case-insensitive
    substring + keyword overlap). Not fancy, but fast and explainable.
    The real intelligence lives in the Claude-driven conversation around
    the verdict -- the script just exposes the locked state for comparison.
  * Markdown rendering uses string substitution, not Jinja or similar.
    Keeps the skill dependency-free like the rest of the suite.
  * Discovers the main profile via the standard suite path. Will fail
    loudly if the profile doesn't exist (scope can't be locked for a
    project that hasn't been onboarded).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


# --------------------------------------------------------------------------- #
# Paths                                                                       #
#                                                                             #
# This skill lives at /mnt/skills/user/mvp-scope-guardian/ and the suite      #
# lives at /mnt/skills/user/solo-dev-suite/. We resolve the suite path by     #
# looking for a sibling directory, which is robust to suite/skill relocation  #
# as long as they stay siblings under the same skills root.                   #
# --------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent       # .../mvp-scope-guardian/scripts
SKILL_DIR = SCRIPT_DIR.parent                       # .../mvp-scope-guardian
TEMPLATES_DIR = SKILL_DIR / "templates"
SCHEMA_PATH = TEMPLATES_DIR / "scope.schema.json"
SCOPE_MD_TMPL = TEMPLATES_DIR / "MVP_SCOPE.md.tmpl"
PARKING_MD_TMPL = TEMPLATES_DIR / "MVP_PARKING_LOT.md.tmpl"


def _find_suite_dir() -> Path:
    """Locate solo-dev-suite as a sibling of this skill's directory.

    If the user has laid out their skills folder differently, they can
    override with the SOLO_DEV_SUITE_DIR env var. We raise a clear error
    if nothing works -- the suite MUST be discoverable for scope to persist.
    """
    import os
    env = os.environ.get("SOLO_DEV_SUITE_DIR")
    if env:
        p = Path(env).resolve()
        if p.is_dir():
            return p

    # Standard layout: sibling of the skill folder.
    sibling = SKILL_DIR.parent / "solo-dev-suite"
    if sibling.is_dir():
        return sibling

    # Walk up a couple of levels in case the layout is nested differently.
    for ancestor in SKILL_DIR.parents:
        candidate = ancestor / "solo-dev-suite"
        if candidate.is_dir():
            return candidate

    raise FileNotFoundError(
        "Could not find solo-dev-suite directory. "
        "Set SOLO_DEV_SUITE_DIR env var or place the suite as a sibling of this skill."
    )


SUITE_DIR = _find_suite_dir()
PROFILES_DIR = SUITE_DIR / "profiles"


# --------------------------------------------------------------------------- #
# Small utilities                                                             #
# --------------------------------------------------------------------------- #

def _err(msg: str) -> None:
    """Tagged stderr output so pipeline consumers can grep for errors."""
    print(f"[scope_tool] {msg}", file=sys.stderr)


def _now_iso() -> str:
    """UTC ISO 8601 timestamp, second precision, no trailing Z.

    Matches the patterns in scope.schema.json and profile.schema.json --
    keeping them consistent across the suite avoids format confusion.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _human_date(iso: Optional[str]) -> str:
    """Turn an ISO timestamp into something human-readable for Markdown output."""
    if not iso:
        return "(not set)"
    try:
        dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%B %d, %Y at %H:%M UTC")
    except ValueError:
        return iso


def _profile_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.json"


def _scope_path(slug: str) -> Path:
    return PROFILES_DIR / f"{slug}.scope.json"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load a JSON file. Returns None if missing, exits if malformed."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _err(f"{path} is corrupted: {e}")
        sys.exit(3)


def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON atomically via .tmp + rename so a crash can't corrupt the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_stdin_json() -> Dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        _err("Expected JSON on stdin, got nothing.")
        sys.exit(5)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        _err(f"stdin is not valid JSON: {e}")
        sys.exit(5)
    if not isinstance(obj, dict):
        _err(f"stdin JSON must be an object, got {type(obj).__name__}.")
        sys.exit(5)
    return obj


# --------------------------------------------------------------------------- #
# JSON Schema validation (same minimal inline validator as profile_io.py)     #
#                                                                             #
# Duplicated intentionally -- each skill should be self-contained and not      #
# depend on the suite's internals. If the validator's behavior needs to       #
# change in both places, a shared util module is the next refactor.           #
# --------------------------------------------------------------------------- #

def _type_matches(value: Any, type_spec: Any) -> bool:
    type_map = {
        "string": str, "integer": int, "number": (int, float),
        "array": list, "object": dict, "boolean": bool, "null": type(None),
    }
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    for t in types:
        py = type_map.get(t)
        if py is None:
            continue
        if t == "integer" and isinstance(value, bool):
            continue
        if isinstance(value, py):
            return True
    return False


def _validate_value(value: Any, schema: Dict[str, Any], path: str, errors: List[str]) -> None:
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {value!r}")
        return
    if "type" in schema and not _type_matches(value, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']}, got {type(value).__name__}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")
        return
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: length {len(value)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: length {len(value)} > maxLength {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match pattern {schema['pattern']!r}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: {len(value)} items < minItems {schema['minItems']}")
        if schema.get("uniqueItems") and len(value) != len({json.dumps(v, sort_keys=True) for v in value}):
            errors.append(f"{path}: items are not unique")
        if "items" in schema:
            for i, item in enumerate(value):
                _validate_value(item, schema["items"], f"{path}[{i}]", errors)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required property '{req}'")
        additional = schema.get("additionalProperties", True)
        for k, v in value.items():
            sub_path = f"{path}.{k}" if path else k
            if k in props:
                _validate_value(v, props[k], sub_path, errors)
            else:
                if additional is False:
                    errors.append(f"{path}: unknown property '{k}'")
                elif isinstance(additional, dict):
                    _validate_value(v, additional, sub_path, errors)


def _validate_scope(scope: Dict[str, Any]) -> List[str]:
    if not SCHEMA_PATH.exists():
        _err(f"Schema not found at {SCHEMA_PATH}. Skill install is broken.")
        sys.exit(2)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors: List[str] = []
    _validate_value(scope, schema, "", errors)
    return errors


# --------------------------------------------------------------------------- #
# ID assignment                                                               #
#                                                                             #
# Feature IDs are stable and prefixed per bucket: LB/PL/PK/WB + zero-padded   #
# counter. We auto-assign them on write so callers never have to think about  #
# collisions. If an entry already has a valid ID we preserve it.              #
# --------------------------------------------------------------------------- #

_BUCKET_PREFIXES = {
    "launch_blocking": "LB",
    "post_launch_v1":  "PL",
    "parking_lot":     "PK",
    "wont_build":      "WB",
}


def _assign_ids(buckets: Dict[str, List[Dict[str, Any]]]) -> None:
    """Ensure every item in every bucket has a unique, valid ID. Mutates in place."""
    for bucket_name, items in buckets.items():
        prefix = _BUCKET_PREFIXES.get(bucket_name)
        if prefix is None:
            continue
        # Collect existing valid IDs to avoid re-issuing them.
        existing = {it["id"] for it in items if isinstance(it.get("id"), str) and re.fullmatch(f"{prefix}\\d{{2,}}", it["id"])}
        # Compute next counter starting from the highest existing.
        max_n = 0
        for eid in existing:
            try:
                max_n = max(max_n, int(eid[len(prefix):]))
            except ValueError:
                pass
        counter = max_n
        for it in items:
            if not (isinstance(it.get("id"), str) and re.fullmatch(f"{prefix}\\d{{2,}}", it["id"])):
                counter += 1
                # Zero-pad to 2 digits minimum (LB01, LB02, ...). Grows naturally.
                it["id"] = f"{prefix}{counter:02d}"


def _stamp_added_at(buckets: Dict[str, List[Dict[str, Any]]]) -> None:
    """Parking-lot items carry an added_at timestamp if not supplied.

    This lets us later prune stale parking-lot items by age.
    """
    now = _now_iso()
    for it in buckets.get("parking_lot", []):
        it.setdefault("added_at", now)


# --------------------------------------------------------------------------- #
# Profile helpers                                                             #
# --------------------------------------------------------------------------- #

def _load_profile(slug: str) -> Dict[str, Any]:
    """Load the main profile. Exits if missing -- scope can't exist without a profile."""
    p = _profile_path(slug)
    profile = _read_json(p)
    if profile is None:
        _err(f"No profile for slug '{slug}' at {p}.")
        _err("Onboard the project via the solo-dev-suite orchestrator first.")
        sys.exit(8)
    return profile


def _update_profile_last_run(slug: str, skill_name: str) -> None:
    """Append/overwrite last_skill_run[skill_name] = now on the main profile."""
    p = _profile_path(slug)
    profile = _read_json(p) or {}
    runs = profile.get("last_skill_run", {})
    runs[skill_name] = _now_iso()
    profile["last_skill_run"] = runs
    profile["updated_at"] = _now_iso()
    _write_json_atomic(p, profile)


# --------------------------------------------------------------------------- #
# Sidecar I/O                                                                 #
# --------------------------------------------------------------------------- #

def _write_sidecar(slug: str, scope: Dict[str, Any]) -> None:
    """Validate and persist the sidecar. Assigns IDs and stamps timestamps first."""
    _assign_ids(scope["buckets"])
    _stamp_added_at(scope["buckets"])

    errors = _validate_scope(scope)
    if errors:
        _err("Sidecar validation failed:")
        for e in errors:
            _err(f"  - {e}")
        sys.exit(4)

    _write_json_atomic(_scope_path(slug), scope)


def _load_sidecar(slug: str) -> Dict[str, Any]:
    sidecar = _read_json(_scope_path(slug))
    if sidecar is None:
        _err(f"No locked scope for '{slug}'. Run `scope_tool.py lock {slug}` first.")
        sys.exit(10)
    return sidecar


# --------------------------------------------------------------------------- #
# Markdown rendering                                                          #
# --------------------------------------------------------------------------- #

def _render_launch_blocking_table(items: List[Dict[str, Any]]) -> str:
    """Render the launch-blocking features as a Markdown table.

    Empty state is a weak smell -- a locked scope with zero launch-blocking
    items means either a trivial project or a user gaming the system.
    """
    if not items:
        return "_(No launch-blocking features. That's suspicious -- either this is a trivial project or you're deferring everything to post-launch.)_\n"
    lines = [
        "| ID | Feature | Effort | Impact | Rationale |",
        "|----|---------|--------|--------|-----------|",
    ]
    for it in items:
        # Escape pipe chars in free-text fields so table rendering doesn't break.
        safe_name = it["name"].replace("|", "\\|")
        safe_rationale = it["rationale"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{it['id']}` | **{safe_name}** | {it['effort']} | {it['impact']} | {safe_rationale} |"
        )
    return "\n".join(lines)


def _render_wont_build_block(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "_(Nothing explicitly rejected. That's a warning sign -- a lock without NOs usually means you didn't push hard enough.)_\n"
    lines = []
    for it in items:
        lines.append(f"### ❌ {it['name']}  \n_`{it['id']}`_\n\n{it['reason']}\n")
    return "\n".join(lines)


def _render_post_launch_block(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "_(No post-launch V1.1 commitments. That's fine -- means you have less pressure after ship.)_\n"
    lines = []
    for it in items:
        wave = it.get("target_wave", "next wave")
        lines.append(f"- `{it['id']}` **{it['name']}** _(target: {wave})_  \n  {it['description']}")
    return "\n".join(lines)


def _render_parking_lot_block(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "_(Parking lot is empty. Either you're disciplined or you haven't brainstormed enough yet.)_\n"
    lines = []
    for it in items:
        added = it.get("added_at", "")[:10]  # just the date portion
        date_suffix = f" _(added {added})_" if added else ""
        lines.append(f"- `{it['id']}` **{it['name']}**{date_suffix}  \n  {it['description']}")
    return "\n".join(lines)


def _render_rescope_history_block(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "_(No rescopes yet. Initial lock is still in force.)_\n"
    lines = []
    for entry in history:
        when = _human_date(entry["at"])
        lines.append(f"### {when}\n\n**Change**: {entry['change']}  \n**Reason**: {entry['reason']}\n")
    return "\n".join(lines)


def _effort_warning(counts: Dict[str, int], profile: Dict[str, Any]) -> str:
    """Surface capacity warnings: too many XLs, or rough hours math that doesn't work."""
    warnings = []
    if counts["XL"] >= 3:
        warnings.append(f"⚠️ **{counts['XL']} XL-effort features** in launch-blocking. Each is 2+ weeks solo. Consider whether all really need to ship v1.")
    # Rough sanity check on timeline if we have data.
    hours = profile.get("available_hours_per_week")
    launch_target = profile.get("launch_target_date")
    if hours and launch_target:
        try:
            target_dt = datetime.strptime(launch_target, "%Y-%m-%d")
            now = datetime.now()
            weeks_left = max(0, (target_dt - now).days // 7)
            # Very rough effort-to-weeks conversion: S=0.2, M=0.6, L=1.5, XL=3 weeks of solo work
            effort_weeks = (counts["S"] * 0.2 + counts["M"] * 0.6 + counts["L"] * 1.5 + counts["XL"] * 3.0)
            # Factor in hours-per-week vs a "full-time" 40-hour baseline
            effort_weeks_adj = effort_weeks * (40.0 / max(hours, 1))
            if effort_weeks_adj > weeks_left and weeks_left > 0:
                warnings.append(
                    f"⚠️ **Rough timeline check**: ~{effort_weeks_adj:.0f} solo-weeks of work estimated at {hours} hrs/week, "
                    f"but only {weeks_left} weeks until launch target. Either cut scope, extend the date, or accept slip."
                )
        except ValueError:
            pass
    if not warnings:
        return "_No capacity warnings. Proceed._\n"
    return "\n\n".join(warnings)


def _render_markdown(
    sidecar: Dict[str, Any],
    profile: Dict[str, Any],
    output_dir: Path,
) -> Tuple[Path, Path]:
    """Render both Markdown docs from the sidecar + profile. Returns output paths."""
    output_dir.mkdir(parents=True, exist_ok=True)

    buckets = sidecar["buckets"]
    lb = buckets["launch_blocking"]

    # Effort counts feed the summary section.
    effort_counts = {"S": 0, "M": 0, "L": 0, "XL": 0}
    for it in lb:
        effort_counts[it["effort"]] = effort_counts.get(it["effort"], 0) + 1

    launch_target = profile.get("launch_target_date")
    launch_target_display = launch_target if launch_target else "_(not set -- run `profile_io.py update <slug>` to add one)_"

    # ---- MVP_SCOPE.md ---- #
    scope_tmpl = SCOPE_MD_TMPL.read_text(encoding="utf-8")
    scope_md = scope_tmpl
    substitutions = {
        "project_name": profile["project_name"],
        "project_slug": sidecar["project_slug"],
        "current_phase": profile["current_phase"],
        "launch_target_display": launch_target_display,
        "locked_at_human": _human_date(sidecar["locked_at"]),
        "launch_blocking_count": str(len(lb)),
        "launch_blocking_table": _render_launch_blocking_table(lb),
        "effort_s_count": str(effort_counts["S"]),
        "effort_m_count": str(effort_counts["M"]),
        "effort_l_count": str(effort_counts["L"]),
        "effort_xl_count": str(effort_counts["XL"]),
        "effort_warning_block": _effort_warning(effort_counts, profile),
        "wont_build_block": _render_wont_build_block(buckets["wont_build"]),
        "schema_version": str(sidecar["schema_version"]),
    }
    for k, v in substitutions.items():
        scope_md = scope_md.replace("{{" + k + "}}", v)

    scope_path = output_dir / "MVP_SCOPE.md"
    scope_path.write_text(scope_md, encoding="utf-8")

    # ---- MVP_PARKING_LOT.md ---- #
    parking_tmpl = PARKING_MD_TMPL.read_text(encoding="utf-8")
    parking_md = parking_tmpl
    rendered_at = _now_iso()
    parking_subs = {
        "project_name": profile["project_name"],
        "project_slug": sidecar["project_slug"],
        "last_rendered_at_human": _human_date(rendered_at),
        "post_launch_block": _render_post_launch_block(buckets["post_launch_v1"]),
        "parking_lot_block": _render_parking_lot_block(buckets["parking_lot"]),
        "rescope_history_block": _render_rescope_history_block(sidecar.get("rescope_history", [])),
    }
    for k, v in parking_subs.items():
        parking_md = parking_md.replace("{{" + k + "}}", v)

    parking_path = output_dir / "MVP_PARKING_LOT.md"
    parking_path.write_text(parking_md, encoding="utf-8")

    # Record the render timestamp back on the sidecar.
    sidecar["last_rendered_at"] = rendered_at
    _write_json_atomic(_scope_path(sidecar["project_slug"]), sidecar)

    return scope_path, parking_path


def _resolve_output_dir(profile: Dict[str, Any], slug: str, override: Optional[str]) -> Path:
    """Figure out where to write the Markdown docs.

    Priority:
      1. Explicit --output-dir from the caller.
      2. <repository_path>/docs/ if the repo exists on this machine.
      3. Fallback staging dir: <suite>/profiles/<slug>_docs/ so the docs
         exist somewhere even when the repo is on another box.
    """
    if override:
        return Path(override).expanduser().resolve()
    repo_path = profile.get("repository_path")
    if repo_path:
        repo = Path(repo_path).expanduser()
        if repo.is_dir():
            return repo / "docs"
        _err(f"Repo path {repo} not reachable from this machine -- falling back to staging.")
    return PROFILES_DIR / f"{slug}_docs"


# --------------------------------------------------------------------------- #
# Scope creep check                                                           #
#                                                                             #
# We compare the candidate feature against every entry in every bucket using  #
# two cheap signals:                                                          #
#                                                                             #
#   1. Case-insensitive substring match on name.                              #
#   2. Keyword overlap: at least 2 shared non-stopword tokens.                #
#                                                                             #
# The hit list is ranked: wont_build > parking_lot > post_launch_v1 >         #
# launch_blocking (already-done). The Claude conversation around the verdict  #
# is where nuance lives -- this script just exposes the raw comparison data.   #
# --------------------------------------------------------------------------- #

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "of", "to", "in", "on", "at",
    "by", "with", "is", "are", "be", "can", "will", "should", "their", "any",
    "all", "some", "this", "that", "these", "those", "it", "its",
}


def _tokenize(text: str) -> List[str]:
    """Lowercase alphanum tokens longer than 2 chars, minus stopwords."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 2 and t not in _STOPWORDS]


def _score_match(candidate_name: str, candidate_desc: str, item: Dict[str, Any]) -> float:
    """Return a simple match score between 0.0 and 1.0."""
    item_name = item.get("name", "")
    item_text = " ".join([
        item_name,
        item.get("description", ""),
        item.get("reason", ""),
        item.get("rationale", ""),
    ])

    score = 0.0
    # Substring hits (either direction) are a strong signal.
    if candidate_name.lower() in item_name.lower() or item_name.lower() in candidate_name.lower():
        score += 0.6

    cand_tokens = set(_tokenize(f"{candidate_name} {candidate_desc}"))
    item_tokens = set(_tokenize(item_text))
    if cand_tokens and item_tokens:
        overlap = cand_tokens & item_tokens
        if len(overlap) >= 2:
            score += 0.3 + (0.1 * min(len(overlap) - 2, 3))  # cap growth
    return min(score, 1.0)


def _creep_check(sidecar: Dict[str, Any], name: str, description: str, threshold: float = 0.4) -> Dict[str, Any]:
    """Return a structured verdict object for the Claude conversation to interpret."""
    buckets = sidecar["buckets"]
    hits: Dict[str, List[Dict[str, Any]]] = {
        "wont_build": [],
        "parking_lot": [],
        "post_launch_v1": [],
        "launch_blocking": [],
    }
    for bucket_name in hits:
        for item in buckets.get(bucket_name, []):
            s = _score_match(name, description, item)
            if s >= threshold:
                hits[bucket_name].append({"item": item, "score": round(s, 2)})

    # Determine highest-priority verdict.
    if hits["wont_build"]:
        verdict = "red"
        summary = "Matches something you explicitly said NO to during the lock."
    elif hits["launch_blocking"]:
        verdict = "duplicate"
        summary = "This is already in the launch-blocking set. No action needed."
    elif hits["post_launch_v1"] or hits["parking_lot"]:
        verdict = "yellow"
        summary = "Already scoped, just not for launch. Pulling forward requires a trade."
    else:
        verdict = "new"
        summary = "Not found in any bucket. Run the Three Killer Questions before adding."

    return {"verdict": verdict, "summary": summary, "hits": hits, "threshold": threshold}


# --------------------------------------------------------------------------- #
# Commands                                                                    #
# --------------------------------------------------------------------------- #

def cmd_lock(args: argparse.Namespace) -> int:
    """Create the initial sidecar from JSON on stdin.

    Expected stdin shape (minimum):
        {
          "buckets": {
            "launch_blocking": [...],
            "post_launch_v1": [...],
            "parking_lot": [...],
            "wont_build": [...]
          }
        }

    Missing buckets default to empty arrays. IDs are auto-assigned.
    """
    slug = args.slug
    _load_profile(slug)  # Fails early if no profile exists.

    if _scope_path(slug).exists() and not args.force:
        _err(f"Scope already locked for '{slug}'. Use `rescope` to modify, or pass --force to re-lock (destroys history).")
        return 7

    payload = _read_stdin_json()
    buckets_in = payload.get("buckets", {})
    now = _now_iso()

    # Normalize into the canonical shape -- all four buckets present.
    normalized_buckets = {
        "launch_blocking": list(buckets_in.get("launch_blocking", [])),
        "post_launch_v1":  list(buckets_in.get("post_launch_v1", [])),
        "parking_lot":     list(buckets_in.get("parking_lot", [])),
        "wont_build":      list(buckets_in.get("wont_build", [])),
    }

    # Default optional fields so validation passes.
    for it in normalized_buckets["parking_lot"]:
        it.setdefault("added_at", now)
    for it in normalized_buckets["post_launch_v1"]:
        it.setdefault("target_wave", "v1.1")

    sidecar = {
        "schema_version": 1,
        "project_slug": slug,
        "locked_at": now,
        "last_rendered_at": None,
        "buckets": normalized_buckets,
        "rescope_history": [],
    }

    _write_sidecar(slug, sidecar)

    # Render docs immediately -- locked scope without docs is useless.
    profile = _load_profile(slug)
    output_dir = _resolve_output_dir(profile, slug, None)
    scope_path, parking_path = _render_markdown(
        _load_sidecar(slug), profile, output_dir
    )

    _update_profile_last_run(slug, "mvp-scope-guardian")

    print(f"Locked scope  : {_scope_path(slug)}")
    print(f"MVP_SCOPE.md  : {scope_path}")
    print(f"PARKING_LOT   : {parking_path}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    sidecar = _load_sidecar(args.slug)
    if args.json:
        print(json.dumps(sidecar, indent=2))
        return 0

    profile = _load_profile(args.slug)
    buckets = sidecar["buckets"]

    print(f"\n  {profile['project_name']}  ({args.slug}) -- Locked Scope")
    print(f"  {'-' * (len(profile['project_name']) + len(args.slug) + 20)}")
    print(f"  Locked    : {_human_date(sidecar['locked_at'])}")
    print(f"  Rendered  : {_human_date(sidecar.get('last_rendered_at'))}")
    print(f"  Rescopes  : {len(sidecar.get('rescope_history', []))}")

    for bucket_name, emoji in [
        ("launch_blocking", "🔒"),
        ("post_launch_v1", "🟢"),
        ("parking_lot", "🗃️ "),
        ("wont_build", "❌"),
    ]:
        items = buckets[bucket_name]
        label = bucket_name.replace("_", " ").upper()
        print(f"\n  {emoji} {label}  ({len(items)})")
        print(f"  {'-' * (len(label) + 6)}")
        if not items:
            print("     (empty)")
            continue
        for it in items:
            extra = ""
            if bucket_name == "launch_blocking":
                extra = f"  [{it['effort']}/{it['impact']}]"
            print(f"     {it['id']}  {it['name']}{extra}")
    print()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    sidecar = _load_sidecar(args.slug)
    result = _creep_check(sidecar, args.feature, args.description or "", threshold=args.threshold)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    verdict_colors = {"red": "🛑", "yellow": "🟡", "duplicate": "🔁", "new": "✨"}
    icon = verdict_colors.get(result["verdict"], "❓")
    print(f"\n  {icon} Verdict: {result['verdict'].upper()}")
    print(f"     {result['summary']}\n")

    for bucket_name, hits in result["hits"].items():
        if not hits:
            continue
        print(f"  Matches in {bucket_name}:")
        for h in hits:
            it = h["item"]
            print(f"     - ({h['score']:.2f}) {it['id']}  {it['name']}")
            if bucket_name == "wont_build" and it.get("reason"):
                print(f"          ↳ reason: {it['reason']}")
            elif it.get("description"):
                print(f"          ↳ {it['description']}")
        print()
    return 0


def cmd_rescope(args: argparse.Namespace) -> int:
    """Apply a patch to the locked scope, recording the change in history.

    Expected stdin shape:
        {
          "change": "human description of what's moving",
          "reason": "why this rescope is legitimate",
          "patch": {
            "launch_blocking": {"add": [...], "remove_ids": ["LB02"]},
            "post_launch_v1":  {"add": [...], "remove_ids": []},
            "parking_lot":     {"add": [...], "remove_ids": []},
            "wont_build":      {"add": [...], "remove_ids": []}
          }
        }

    The patch semantics are per-bucket: add items + remove-by-id. Simple
    and explicit -- no clever move operations. To move an item, remove it
    from one bucket and add its content to another.
    """
    slug = args.slug
    sidecar = _load_sidecar(slug)
    payload = _read_stdin_json()

    change = payload.get("change", "").strip()
    reason = payload.get("reason", "").strip()
    if not change or not reason:
        _err("Rescope payload must include non-empty 'change' and 'reason' fields.")
        return 11

    patch = payload.get("patch", {})
    buckets = sidecar["buckets"]

    for bucket_name in _BUCKET_PREFIXES:
        bucket_patch = patch.get(bucket_name, {})
        remove_ids = set(bucket_patch.get("remove_ids", []))
        additions = bucket_patch.get("add", [])
        if remove_ids:
            before = len(buckets[bucket_name])
            buckets[bucket_name] = [it for it in buckets[bucket_name] if it.get("id") not in remove_ids]
            removed = before - len(buckets[bucket_name])
            if removed != len(remove_ids):
                _err(f"Note: only removed {removed} of {len(remove_ids)} IDs from {bucket_name} -- some were not found.")
        if additions:
            buckets[bucket_name].extend(additions)

    history = sidecar.setdefault("rescope_history", [])
    history.append({
        "at": _now_iso(),
        "change": change,
        "reason": reason,
    })

    _write_sidecar(slug, sidecar)

    # Re-render docs so files reflect new state.
    profile = _load_profile(slug)
    output_dir = _resolve_output_dir(profile, slug, None)
    scope_path, parking_path = _render_markdown(_load_sidecar(slug), profile, output_dir)

    _update_profile_last_run(slug, "mvp-scope-guardian")

    print(f"Rescope applied. History entries: {len(history)}")
    print(f"MVP_SCOPE.md  : {scope_path}")
    print(f"PARKING_LOT   : {parking_path}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    sidecar = _load_sidecar(args.slug)
    profile = _load_profile(args.slug)
    output_dir = _resolve_output_dir(profile, args.slug, args.output_dir)
    scope_path, parking_path = _render_markdown(sidecar, profile, output_dir)
    print(f"Rendered to   : {output_dir}")
    print(f"  - {scope_path.name}")
    print(f"  - {parking_path.name}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Remove sidecar + rendered docs. Requires --yes to avoid accidents."""
    sidecar_path = _scope_path(args.slug)
    if not sidecar_path.exists():
        _err(f"No scope file for '{args.slug}'.")
        return 8
    if not args.yes:
        _err(f"Delete scope for '{args.slug}'? Re-run with --yes to confirm.")
        return 9
    sidecar_path.unlink()

    # Also try to remove staged docs if any.
    staged = PROFILES_DIR / f"{args.slug}_docs"
    if staged.is_dir():
        for f in staged.iterdir():
            f.unlink()
        staged.rmdir()
    print(f"Deleted scope for '{args.slug}'.")
    return 0


# --------------------------------------------------------------------------- #
# Arg parsing                                                                 #
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scope_tool", description="MVP Scope Guardian CRUD + creep check.")
    sub = p.add_subparsers(dest="command", required=True)

    p_lock = sub.add_parser("lock", help="Create the initial locked scope (reads JSON on stdin).")
    p_lock.add_argument("slug")
    p_lock.add_argument("--from-stdin", action="store_true", required=True)
    p_lock.add_argument("--force", action="store_true", help="Overwrite an existing lock (destroys history).")
    p_lock.set_defaults(func=cmd_lock)

    p_show = sub.add_parser("show", help="Display the locked scope.")
    p_show.add_argument("slug")
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_check = sub.add_parser("check", help="Scope creep verdict for a candidate feature.")
    p_check.add_argument("slug")
    p_check.add_argument("--feature", required=True, help="Candidate feature name.")
    p_check.add_argument("--description", default="", help="Candidate feature description (improves match quality).")
    p_check.add_argument("--threshold", type=float, default=0.4, help="Match score threshold 0.0-1.0 (default 0.4).")
    p_check.add_argument("--json", action="store_true")
    p_check.set_defaults(func=cmd_check)

    p_rescope = sub.add_parser("rescope", help="Apply a patch with recorded rationale (reads JSON on stdin).")
    p_rescope.add_argument("slug")
    p_rescope.add_argument("--from-stdin", action="store_true", required=True)
    p_rescope.set_defaults(func=cmd_rescope)

    p_render = sub.add_parser("render", help="Re-generate Markdown docs from the sidecar.")
    p_render.add_argument("slug")
    p_render.add_argument("--output-dir", help="Override the default output location.")
    p_render.set_defaults(func=cmd_render)

    p_delete = sub.add_parser("delete", help="Remove sidecar + rendered docs.")
    p_delete.add_argument("slug")
    p_delete.add_argument("--yes", action="store_true")
    p_delete.set_defaults(func=cmd_delete)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
