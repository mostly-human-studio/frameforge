import json

import pytest

from conftest import write_creative
from frameforge.errors import ApprovalRequired, CorruptState, FrameForgeError, MissingArtifact, ProjectNotFound
from frameforge.hashing import hash_data
from frameforge.state import STAGES, ApprovalGate, StageStatus, Workspace


def test_create_lays_out_project_and_snapshots_profile(workspace):
    p = workspace.create("Explain how an AI agent works", project_id="demo")
    d = workspace.dir("demo")
    for sub in ("assets", "audio", "scenes", "review", "output"):
        assert (d / sub).is_dir()
    assert (d / "design-system.yaml").is_file()
    assert p.profile.name == "technical-dark" and p.profile.version == 2
    assert p.stages["setup"].status is StageStatus.done
    assert set(p.stages) == set(STAGES)


def test_generated_id_is_slug_plus_suffix(workspace):
    p = workspace.create("Explain How an AI Agent Works!")
    assert p.id.startswith("explain-how-an-ai-agent-works-")


def test_duplicate_project_rejected(workspace):
    workspace.create("x", project_id="dup")
    with pytest.raises(FrameForgeError, match="already exists"):
        workspace.create("x", project_id="dup")


@pytest.mark.parametrize("bad", ["../escape", "Upper", "a/b", "", "-lead"])
def test_invalid_ids_rejected(workspace, bad):
    with pytest.raises(FrameForgeError, match="Invalid project id"):
        workspace.create("x", project_id=bad)


def test_unknown_profile_has_actionable_error(workspace):
    with pytest.raises(FrameForgeError) as exc:
        workspace.create("x", project_id="p", profile="nope")
    assert "technical-dark" in exc.value.hint


def test_profile_snapshot_isolated_from_later_edits(workspace):
    workspace.create("x", project_id="iso")
    shared = workspace.root / "config" / "profiles" / "technical-dark.yaml"
    shared.write_text(shared.read_text() + "\n# edited later\n")
    snap = (workspace.dir("iso") / "design-system.yaml").read_text()
    assert "edited later" not in snap


# --- AT6: resume after interruption without losing approvals ---

def test_resume_preserves_stages_and_approvals(workspace):
    p = workspace.create("x", project_id="resume")
    write_creative(workspace, "resume")
    workspace.mark_stage(p, "brief", StageStatus.done, outputs=["brief.md"])
    workspace.approve(p, ApprovalGate.creative, note="looks good")

    fresh = Workspace(workspace.root).load("resume")  # new process, same disk
    assert fresh.stages["brief"].status is StageStatus.done
    assert fresh.stages["brief"].outputs["brief.md"]
    assert fresh.approvals[ApprovalGate.creative].note == "looks good"
    assert workspace.check_approval(fresh, ApprovalGate.creative).state == "valid"


def test_atomic_write_leaves_no_temp_files(workspace):
    p = workspace.create("x", project_id="atomic")
    for _ in range(5):
        workspace.save(p)
    leftovers = [f.name for f in workspace.dir("atomic").iterdir() if f.name.endswith(".tmp")]
    assert leftovers == []


def test_missing_project_lists_known(workspace):
    workspace.create("x", project_id="known")
    with pytest.raises(ProjectNotFound) as exc:
        workspace.load("unknown")
    assert "known" in exc.value.hint


def test_corrupt_state_reported_not_crashed(workspace):
    workspace.create("x", project_id="bad")
    workspace.state_path("bad").write_text("{not json")
    with pytest.raises(CorruptState):
        workspace.load("bad")


def test_newer_schema_refused(workspace):
    workspace.create("x", project_id="future")
    path = workspace.state_path("future")
    data = json.loads(path.read_text())
    data["schema_version"] = 99
    path.write_text(json.dumps(data))
    with pytest.raises(CorruptState, match="newer"):
        workspace.load("future")


# --- Approval gates bound to content hashes ---

def test_approve_requires_all_creative_artifacts(workspace):
    p = workspace.create("x", project_id="gate")
    with pytest.raises(MissingArtifact) as exc:
        workspace.approve(p, ApprovalGate.creative)
    assert "storyboard.json" in exc.value.message


def test_unapproved_build_blocked(workspace):
    p = workspace.create("x", project_id="blocked")
    write_creative(workspace, "blocked")
    with pytest.raises(ApprovalRequired, match="not been recorded"):
        workspace.require_approval(p, ApprovalGate.creative)


def test_editing_approved_file_voids_approval(workspace):
    p = workspace.create("x", project_id="edit")
    write_creative(workspace, "edit")
    workspace.approve(p, ApprovalGate.creative)
    workspace.require_approval(p, ApprovalGate.creative)  # valid

    (workspace.dir("edit") / "script.md").write_text("# Script\nScene 1: changed\n")
    check = workspace.check_approval(p, ApprovalGate.creative)
    assert check.state == "stale" and check.changed == ["script.md"]
    with pytest.raises(ApprovalRequired, match="stale"):
        workspace.require_approval(p, ApprovalGate.creative)


def test_reapproval_after_edit_restores_gate(workspace):
    p = workspace.create("x", project_id="reapprove")
    write_creative(workspace, "reapprove")
    workspace.approve(p, ApprovalGate.creative)
    (workspace.dir("reapprove") / "brief.md").write_text("new brief")
    workspace.approve(p, ApprovalGate.creative)
    assert workspace.check_approval(p, ApprovalGate.creative).state == "valid"


def test_deleting_approved_file_voids_approval(workspace):
    p = workspace.create("x", project_id="deleted")
    write_creative(workspace, "deleted")
    workspace.approve(p, ApprovalGate.creative)
    (workspace.dir("deleted") / "storyboard.json").unlink()
    assert workspace.check_approval(p, ApprovalGate.creative).changed == ["storyboard.json"]


def test_hash_data_ignores_key_order():
    assert hash_data({"a": 1, "b": [1, 2]}) == hash_data({"b": [1, 2], "a": 1})
