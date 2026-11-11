import json

from typer.testing import CliRunner

from conftest import write_creative
from frameforge.cli import app

runner = CliRunner()


def run(*args):
    return runner.invoke(app, list(args))


def test_create_status_roundtrip(workspace):
    r = run("create", "Explain how an AI agent works", "--duration", "60", "--id", "cli")
    assert r.exit_code == 0, r.output
    assert "cli" in r.stdout

    r = run("status", "cli", "--json")
    data = json.loads(r.stdout)
    assert data["settings"]["duration_s"] == 60
    assert data["approval_checks"]["creative"]["state"] == "missing"

    r = run("list")
    assert r.stdout.split() == ["cli"]


def test_build_blocked_until_creative_approval(workspace):
    run("create", "x", "--id", "gate")
    write_creative(workspace, "gate")

    r = run("build", "gate")
    assert r.exit_code == 3
    assert "approve gate --stage creative" in r.stderr

    assert run("approve", "gate", "--stage", "creative").exit_code == 0
    r = run("build", "gate")
    assert r.exit_code == 0, r.output
    assert (workspace.dir("gate") / "output" / "final.mp4").is_file()


def test_errors_are_clean_with_hints(workspace):
    r = run("status", "nope")
    assert r.exit_code == 2
    assert "Hint:" in r.stderr
    assert "Traceback" not in r.output


def test_bad_aspect_rejected(workspace):
    r = run("create", "x", "--aspect", "4:3")
    assert r.exit_code == 1 and "16:9" in r.stderr
