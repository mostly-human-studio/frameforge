"""Persistent project state: project.json model, atomic IO and approval gates.

Approvals are bound to content hashes. An approval is valid only while every
file it was granted against still hashes the same, so editing an approved
artifact voids the approval without anyone having to remember to revoke it.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from .errors import ApprovalRequired, CorruptState, FrameForgeError, MissingArtifact, ProjectNotFound
from .hashing import hash_file
from .paths import CREATIVE_ARTIFACTS, PROJECT_SUBDIRS, project_dir, projects_dir
from .profiles import snapshot_profile

SCHEMA_VERSION = 1
STATE_FILE = "project.json"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

STAGES = ("setup", "brief", "script", "design", "storyboard", "art", "voice", "build", "review")

FINAL_ARTIFACTS = ("output/final.mp4", "review/report.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StageStatus(str, Enum):
    pending = "pending"
    done = "done"
    failed = "failed"
    stale = "stale"


class ApprovalGate(str, Enum):
    creative = "creative"
    final = "final"


GATE_ARTIFACTS: dict[ApprovalGate, tuple[str, ...]] = {
    ApprovalGate.creative: CREATIVE_ARTIFACTS,
    ApprovalGate.final: FINAL_ARTIFACTS,
}


class StageState(BaseModel):
    status: StageStatus = StageStatus.pending
    input_hash: str | None = None
    outputs: dict[str, str] = Field(default_factory=dict)  # relpath -> hash
    updated_at: str | None = None
    error: str | None = None


class Approval(BaseModel):
    approved_at: str
    bound: dict[str, str]  # relpath -> hash at approval time
    note: str | None = None


class ProfileRef(BaseModel):
    name: str
    version: int | str
    hash: str


class Settings(BaseModel):
    duration_s: int = 60
    aspect: str = "16:9"
    fps: int = 30


class Project(BaseModel):
    schema_version: int = SCHEMA_VERSION
    id: str
    concept: str
    created_at: str
    updated_at: str
    settings: Settings
    profile: ProfileRef
    stages: dict[str, StageState] = Field(default_factory=lambda: {s: StageState() for s in STAGES})
    approvals: dict[ApprovalGate, Approval] = Field(default_factory=dict)
    scenes: dict[str, dict] = Field(default_factory=dict)  # scene-id -> cache keys (M4)


class ApprovalCheck(BaseModel):
    state: str  # "valid" | "stale" | "missing"
    changed: list[str] = Field(default_factory=list)


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:max_len].rstrip("-")) or "project"


class Workspace:
    """All state operations, rooted at a workspace directory."""

    def __init__(self, root: Path):
        self.root = Path(root)

    # ---------- paths ----------
    def dir(self, project_id: str) -> Path:
        _validate_id(project_id)
        return project_dir(project_id, self.root)

    def state_path(self, project_id: str) -> Path:
        return self.dir(project_id) / STATE_FILE

    # ---------- lifecycle ----------
    def create(
        self,
        concept: str,
        *,
        duration_s: int = 60,
        profile: str = "technical-dark",
        aspect: str = "16:9",
        fps: int = 30,
        project_id: str | None = None,
    ) -> Project:
        if not concept.strip():
            raise FrameForgeError("Concept is empty.", hint='Pass a concept, e.g. frameforge create "Explain X".')
        pid = project_id if project_id is not None else f"{slugify(concept)}-{secrets.token_hex(2)}"
        _validate_id(pid)
        pdir = self.dir(pid)
        if pdir.exists():
            raise FrameForgeError(
                f"Project '{pid}' already exists.",
                hint=f"Resume it with 'frameforge status {pid}', or choose a different --id.",
            )
        pdir.mkdir(parents=True)
        for sub in PROJECT_SUBDIRS:
            (pdir / sub).mkdir()
        profile_ref = snapshot_profile(profile, pdir / "design-system.yaml", self.root)

        now = _now()
        project = Project(
            id=pid,
            concept=concept.strip(),
            created_at=now,
            updated_at=now,
            settings=Settings(duration_s=duration_s, aspect=aspect, fps=fps),
            profile=ProfileRef(**profile_ref),
        )
        project.stages["setup"] = StageState(
            status=StageStatus.done,
            outputs={"design-system.yaml": profile_ref["hash"]},
            updated_at=now,
        )
        self.save(project)
        return project

    def load(self, project_id: str) -> Project:
        path = self.state_path(project_id)
        if not path.is_file():
            known = ", ".join(self.list_ids()) or "none"
            raise ProjectNotFound(
                f"No project '{project_id}' in {projects_dir(self.root)}.",
                hint=f"Known projects: {known}. Check FRAMEFORGE_HOME or the current directory.",
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            project = Project.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise CorruptState(
                f"project.json for '{project_id}' is unreadable: {exc.__class__.__name__}.",
                hint="Restore it from version control or backup; artifacts on disk are untouched.",
            ) from exc
        if project.schema_version > SCHEMA_VERSION:
            raise CorruptState(
                f"project.json schema v{project.schema_version} is newer than this FrameForge (v{SCHEMA_VERSION}).",
                hint="Upgrade FrameForge.",
            )
        return project

    def save(self, project: Project) -> None:
        project.updated_at = _now()
        _atomic_write(self.state_path(project.id), project.model_dump_json(indent=2))

    def list_ids(self) -> list[str]:
        d = projects_dir(self.root)
        if not d.is_dir():
            return []
        return sorted(p.name for p in d.iterdir() if (p / STATE_FILE).is_file())

    # ---------- stages ----------
    def mark_stage(
        self,
        project: Project,
        stage: str,
        status: StageStatus,
        *,
        outputs: list[str] | None = None,
        input_hash: str | None = None,
        error: str | None = None,
    ) -> None:
        if stage not in STAGES:
            raise FrameForgeError(f"Unknown stage '{stage}'.", hint=f"Stages: {', '.join(STAGES)}.")
        pdir = self.dir(project.id)
        project.stages[stage] = StageState(
            status=status,
            input_hash=input_hash,
            outputs={rel: hash_file(pdir / rel) or "" for rel in (outputs or [])},
            updated_at=_now(),
            error=error,
        )
        self.save(project)

    # ---------- approvals ----------
    def approve(self, project: Project, gate: ApprovalGate, note: str | None = None) -> Approval:
        pdir = self.dir(project.id)
        bound: dict[str, str] = {}
        missing: list[str] = []
        for rel in GATE_ARTIFACTS[gate]:
            h = hash_file(pdir / rel)
            if h is None:
                missing.append(rel)
            else:
                bound[rel] = h
        if missing:
            raise MissingArtifact(
                f"Cannot approve '{gate.value}': missing {', '.join(missing)}.",
                hint=_gate_hint(gate, project.id),
            )
        approval = Approval(approved_at=_now(), bound=bound, note=note)
        project.approvals[gate] = approval
        self.save(project)
        return approval

    def check_approval(self, project: Project, gate: ApprovalGate) -> ApprovalCheck:
        approval = project.approvals.get(gate)
        if approval is None:
            return ApprovalCheck(state="missing")
        pdir = self.dir(project.id)
        changed = [rel for rel, h in approval.bound.items() if hash_file(pdir / rel) != h]
        return ApprovalCheck(state="stale" if changed else "valid", changed=changed)

    def require_approval(self, project: Project, gate: ApprovalGate) -> None:
        check = self.check_approval(project, gate)
        if check.state == "valid":
            return
        if check.state == "missing":
            msg = f"'{gate.value}' approval has not been recorded."
        else:
            msg = f"'{gate.value}' approval is stale; changed since approval: {', '.join(check.changed)}."
        raise ApprovalRequired(msg, hint=f"Review the files, then run 'frameforge approve {project.id} --stage {gate.value}'.")


def _gate_hint(gate: ApprovalGate, pid: str) -> str:
    if gate is ApprovalGate.creative:
        return f"Run 'frameforge plan {pid}' to generate them (or write them by hand), then approve."
    return f"Run 'frameforge build {pid}' and 'frameforge review {pid}' first."


def _validate_id(project_id: str) -> None:
    if not ID_PATTERN.match(project_id):
        raise FrameForgeError(
            f"Invalid project id '{project_id}'.",
            hint="Use lowercase letters, digits and hyphens (max 64 chars).",
        )


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
