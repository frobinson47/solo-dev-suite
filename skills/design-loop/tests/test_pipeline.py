#!/usr/bin/env python3
"""End-to-end pipeline tests for the design-loop skill.

Runs discover.py -> generate_prompt.py -> validate_prompt.py against each
fixture and asserts:
  - discovery produces the expected project_type and ui_framework
  - generated prompt passes every validator check
  - monorepo without --surface fails loud
  - monorepo with --surface produces surface-specific prompts

Run with: pytest tests/ -v
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURES = SKILL_ROOT / "fixtures"


def run(cmd, check=True):
    """Run a subprocess and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=SKILL_ROOT,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"Command failed ({result.returncode}): {' '.join(str(c) for c in cmd)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.returncode, result.stdout, result.stderr


def discover(fixture_path, surface=None):
    cmd = [sys.executable, str(SCRIPTS / "discover.py"), str(fixture_path)]
    if surface:
        cmd.extend(["--surface", surface])
    _, stdout, _ = run(cmd)
    return json.loads(stdout)


def generate(context_path, surface=None, extra=None):
    cmd = [sys.executable, str(SCRIPTS / "generate_prompt.py"), str(context_path)]
    if surface:
        cmd.extend(["--surface", surface])
    if extra:
        cmd.extend(extra)
    return run(cmd, check=False)


def validate(prompt_path):
    cmd = [sys.executable, str(SCRIPTS / "validate_prompt.py"), "-q", str(prompt_path)]
    return run(cmd, check=False)


# ---------- Single-surface fixtures ----------

SINGLE_SURFACE_CASES = [
    # (fixture_name, expected_project_type, expected_ui_framework_contains)
    ("nextjs-dashboard", "saas-dashboard", {"nextjs", "tailwind", "shadcn"}),
    ("streamlit-app",    "creative",       {"streamlit"}),
    ("static-site",      "marketing",      {"plain-html"}),
]


@pytest.mark.parametrize("fixture,expected_type,expected_ui", SINGLE_SURFACE_CASES)
def test_discovery_matches_expected(fixture, expected_type, expected_ui):
    """Each fixture should be classified as its intended project type."""
    ctx = discover(FIXTURES / fixture)
    assert ctx["project_type"] == expected_type, (
        f"{fixture}: expected project_type={expected_type!r}, got {ctx['project_type']!r}"
    )
    ui_set = set(ctx["ui_framework"])
    missing = expected_ui - ui_set
    assert not missing, (
        f"{fixture}: ui_framework missing {missing}. Got {ui_set}."
    )


@pytest.mark.parametrize("fixture,_expected_type,_expected_ui", SINGLE_SURFACE_CASES)
def test_end_to_end_pipeline(fixture, _expected_type, _expected_ui, tmp_path):
    """discover -> generate -> validate should exit 0 on every fixture."""
    ctx_path = tmp_path / "context.json"
    prompt_path = tmp_path / "LOOP_PROMPT.md"

    ctx = discover(FIXTURES / fixture)
    ctx_path.write_text(json.dumps(ctx, indent=2))

    rc, stdout, stderr = generate(ctx_path)
    assert rc == 0, f"generate_prompt.py failed: {stderr}"
    prompt_path.write_text(stdout)

    rc, _, stderr = validate(prompt_path)
    assert rc == 0, f"validator rejected {fixture} prompt:\n{stderr}"


def test_generated_prompt_has_version_tag(tmp_path):
    """Every prompt should carry the data library version in its header comment."""
    ctx = discover(FIXTURES / "nextjs-dashboard")
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    _, stdout, _ = generate(ctx_path)
    assert "design-loop version: 2026.04" in stdout


def test_generated_prompt_no_unfilled_placeholders(tmp_path):
    """No `{{...}}` should survive templating."""
    ctx = discover(FIXTURES / "streamlit-app")
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    _, stdout, _ = generate(ctx_path)
    assert "{{" not in stdout, f"unfilled placeholder in output:\n{stdout}"
    assert "}}" not in stdout


# ---------- Monorepo handling ----------

def test_monorepo_detects_multiple_surfaces():
    """The monorepo fixture should emit ui_surfaces with both apps listed."""
    ctx = discover(FIXTURES / "monorepo")
    surfaces = {s["path"] for s in ctx["ui_surfaces"]}
    assert "apps/admin" in surfaces
    assert "apps/marketing" in surfaces
    assert ctx.get("_monorepo_warning"), "expected _monorepo_warning when no --surface picked"


def test_monorepo_without_surface_refuses_to_generate(tmp_path):
    """generate_prompt.py must exit non-zero when context has unpicked surfaces."""
    ctx = discover(FIXTURES / "monorepo")
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    rc, _, stderr = generate(ctx_path)
    assert rc != 0, f"expected refusal, got exit 0. stderr:\n{stderr}"
    assert "UI surfaces" in stderr or "surface" in stderr.lower()


def test_monorepo_admin_surface_is_saas_dashboard(tmp_path):
    """apps/admin should be classified as saas-dashboard and pass validation."""
    ctx = discover(FIXTURES / "monorepo", surface="apps/admin")
    assert ctx["project_type"] == "saas-dashboard"
    assert "nextjs" in ctx["ui_framework"]

    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    rc, stdout, _ = generate(ctx_path, surface="apps/admin")
    assert rc == 0
    prompt_path = tmp_path / "LOOP_PROMPT.md"
    prompt_path.write_text(stdout)

    rc, _, stderr = validate(prompt_path)
    assert rc == 0, f"validator rejected admin prompt:\n{stderr}"


def test_monorepo_marketing_surface_is_marketing(tmp_path):
    """apps/marketing should be classified as marketing and get marketing references."""
    ctx = discover(FIXTURES / "monorepo", surface="apps/marketing")
    assert ctx["project_type"] == "marketing"

    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    rc, stdout, _ = generate(ctx_path, surface="apps/marketing")
    assert rc == 0
    # Marketing fixture pulls the marketing reference set
    assert "Apple" in stdout
    assert "Framer" in stdout


def test_surface_mismatch_between_context_and_flag(tmp_path):
    """If --surface on generate doesn't match context.surface, fail loud."""
    ctx = discover(FIXTURES / "monorepo", surface="apps/admin")
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    rc, _, stderr = generate(ctx_path, surface="apps/marketing")
    assert rc != 0
    assert "surface" in stderr.lower()


# ---------- Validator targeted tests ----------

def test_validator_catches_missing_reference(tmp_path):
    """Removing a reference should fail the `references` check."""
    ctx = discover(FIXTURES / "nextjs-dashboard")
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    _, stdout, _ = generate(ctx_path)

    # Drop one reference line
    lines = stdout.splitlines()
    in_refs = False
    dropped = False
    out_lines = []
    for line in lines:
        if line.startswith("## Reference aesthetic"):
            in_refs = True
        elif line.startswith("## "):
            in_refs = False
        if in_refs and line.startswith("- ") and not dropped:
            dropped = True
            continue
        out_lines.append(line)
    prompt_path = tmp_path / "LOOP_PROMPT.md"
    prompt_path.write_text("\n".join(out_lines))

    rc, _, stderr = validate(prompt_path)
    assert rc != 0
    assert "references" in stderr


def test_validator_catches_unfilled_placeholder(tmp_path):
    """Injecting a {{...}} should fail no_placeholders check."""
    ctx = discover(FIXTURES / "nextjs-dashboard")
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    _, stdout, _ = generate(ctx_path)

    prompt_path = tmp_path / "LOOP_PROMPT.md"
    prompt_path.write_text(stdout + "\n{{leftover_placeholder}}\n")

    rc, _, stderr = validate(prompt_path)
    assert rc != 0
    assert "placeholder" in stderr.lower()


def test_validator_catches_missing_mission(tmp_path):
    """Removing the MISSION line should fail the mission check."""
    ctx = discover(FIXTURES / "nextjs-dashboard")
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    _, stdout, _ = generate(ctx_path)

    corrupted = "\n".join(ln for ln in stdout.splitlines() if not ln.startswith("MISSION:"))
    prompt_path = tmp_path / "LOOP_PROMPT.md"
    prompt_path.write_text(corrupted)

    rc, _, stderr = validate(prompt_path)
    assert rc != 0
    assert "mission" in stderr.lower()


# ---------- Override flags ----------

def test_type_override(tmp_path):
    """--type should override auto-detected project_type."""
    ctx = discover(FIXTURES / "nextjs-dashboard")  # would be saas-dashboard
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    rc, stdout, _ = generate(ctx_path, extra=["--type", "creative"])
    assert rc == 0
    # Creative references should appear
    assert "Figma" in stdout or "Ableton Live" in stdout
    # saas references should NOT dominate
    assert "Vercel Dashboard" not in stdout


def test_refs_override_normalizes_to_five(tmp_path):
    """--refs with fewer than 5 entries should pad, more than 5 should trim."""
    ctx = discover(FIXTURES / "nextjs-dashboard")
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))

    # Too few
    rc, stdout, stderr = generate(ctx_path, extra=["--refs", "foo,bar"])
    assert rc == 0
    assert "padding" in stderr.lower()

    # Too many
    rc, stdout, stderr = generate(
        ctx_path, extra=["--refs", "a,b,c,d,e,f,g,h"]
    )
    assert rc == 0
    assert "trimming" in stderr.lower()


def test_runner_flag_appears_in_prompt(tmp_path):
    """--runner value should replace the How-to-run invocation."""
    ctx = discover(FIXTURES / "nextjs-dashboard")
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    rc, stdout, _ = generate(ctx_path, extra=["--runner", "/my-custom-runner"])
    assert rc == 0
    assert "/my-custom-runner" in stdout


def test_hero_override(tmp_path):
    """--hero should replace the hero screen in the convergence clause."""
    ctx = discover(FIXTURES / "nextjs-dashboard")
    ctx_path = tmp_path / "context.json"
    ctx_path.write_text(json.dumps(ctx, indent=2))
    rc, stdout, _ = generate(ctx_path, extra=["--hero", "the billing page"])
    assert rc == 0
    assert "the billing page" in stdout


# ---------- Data library schema ----------

def test_data_libraries_have_version():
    """Both data libraries must carry a version field."""
    for lib_path in (SKILL_ROOT / "data" / "references.json",
                     SKILL_ROOT / "data" / "dimensions.json"):
        data = json.loads(lib_path.read_text())
        assert "version" in data, f"{lib_path.name} missing version"
        assert "project_types" in data, f"{lib_path.name} missing project_types"


def test_all_project_types_covered_in_both_libraries():
    """Every project type must be defined in both references and dimensions."""
    refs = json.loads((SKILL_ROOT / "data" / "references.json").read_text())
    dims = json.loads((SKILL_ROOT / "data" / "dimensions.json").read_text())
    required = {"saas-dashboard", "marketing", "dev-tool", "internal-ops",
                "ecommerce", "creative", "game", "docs", "unknown"}
    assert required <= set(refs["project_types"].keys())
    assert required <= set(dims["project_types"].keys())


def test_every_reference_set_has_exactly_five():
    """references.json contract: each project_type → exactly 5 refs."""
    refs = json.loads((SKILL_ROOT / "data" / "references.json").read_text())
    for ptype, entries in refs["project_types"].items():
        assert len(entries) == 5, f"{ptype} has {len(entries)} refs, expected 5"
