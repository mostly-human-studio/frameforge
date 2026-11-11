"""CLI-level tests for M1: AT1 (concept → brief/script/storyboard) and AT2 (build gated)."""

import json

from typer.testing import CliRunner

from conftest import EXAMPLES
from frameforge.cli import app

runner = CliRunner()
DEMO = str(EXAMPLES / "llm-api-explainer.md")


def run(*args):
    return runner.invoke(app, list(args))


def test_at1_concept_to_creative_files(workspace):
    assert run("create", "How an AI app talks to an LLM API", "--id", "demo").exit_code == 0
    r = run("plan", "demo", "--source", DEMO)
    assert r.exit_code == 0, r.output
    d = workspace.dir("demo")
    for name in ("brief.md", "script.md", "storyboard.json", "source.md"):
        assert (d / name).is_file()
    assert "creative files valid" in r.stderr
    assert run("validate", "demo").exit_code == 0


def test_concept_only_plan_yields_skeleton_that_cannot_be_approved(workspace):
    run("create", "Explain DNS", "--id", "dns")
    r = run("plan", "dns")
    assert r.exit_code == 0 and "TODO" in r.stderr
    r = run("approve", "dns", "--stage", "creative")
    assert r.exit_code == 6 and "placeholder TODO" in r.stderr
    assert json.loads(run("status", "dns", "--json").stdout)["approval_checks"]["creative"]["state"] == "missing"


def test_at2_build_blocked_until_approved_then_after_edit(workspace):
    run("create", "x", "--id", "gate")
    run("plan", "gate", "--source", DEMO)
    assert run("build", "gate").exit_code == 3

    assert run("approve", "gate", "--stage", "creative").exit_code == 0
    r = run("build", "gate")
    assert r.exit_code == 0, r.output

    script = workspace.dir("gate") / "script.md"
    script.write_text(script.read_text() + "\nOne more line.\n")
    r = run("build", "gate")
    assert r.exit_code == 3 and "stale" in r.stderr and "script.md" in r.stderr


def test_plan_never_clobbers_without_force(workspace):
    run("create", "x", "--id", "keep")
    run("plan", "keep", "--source", DEMO)
    brief = workspace.dir("keep") / "brief.md"
    brief.write_text(brief.read_text().replace("a little dry", "very dry"))
    edited = brief.read_text()

    r = run("plan", "keep", "--source", DEMO)
    assert r.exit_code == 1 and "--force" in r.stderr
    assert brief.read_text() == edited

    r = run("plan", "keep", "--source", DEMO, "--force")
    assert r.exit_code == 0
    backups = list((workspace.dir("keep") / "history").glob("*/brief.md"))
    assert len(backups) == 1 and backups[0].read_text() == edited


def test_external_director_writes_brief_and_schemas_only(workspace):
    run("create", "Explain queues", "--id", "ext", "--duration", "90")
    r = run("plan", "ext", "--director", "external")
    assert r.exit_code == 0, r.output
    d = workspace.dir("ext")
    text = (d / "DIRECTOR.md").read_text()
    assert "Explain queues" in text and "225 narration words" in text and "Do not run `frameforge approve`" in text
    assert (d / "schemas" / "storyboard.schema.json").is_file()
    assert not (d / "script.md").exists()


def test_build_requires_assets(workspace):
    run("create", "x", "--id", "assets")
    run("plan", "assets", "--source", DEMO)
    sb = workspace.dir("assets") / "storyboard.json"
    data = json.loads(sb.read_text())
    data["scenes"][2] = {"id": "s03", "template": "image", "props": {"asset": "diagram.png"}}
    sb.write_text(json.dumps(data))
    assert run("approve", "assets", "--stage", "creative").exit_code == 0  # warning only
    r = run("build", "assets")
    assert r.exit_code == 6 and "diagram.png" in r.stderr


def test_missing_source_file(workspace):
    run("create", "x", "--id", "src")
    r = run("plan", "src", "--source", "nope.md")
    assert r.exit_code == 1 and "not found" in r.stderr


def test_schema_command():
    r = run("schema", "storyboard")
    assert r.exit_code == 0
    assert "architecture-diagram" in r.stdout and '"from"' in r.stdout
