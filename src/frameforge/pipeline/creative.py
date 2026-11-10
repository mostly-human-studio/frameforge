"""Creative stage: validate brief/script/storyboard/design and cross-check them.

Used by `frameforge validate`, by `plan` after drafting, and by
`approve --stage creative`, which refuses to approve an invalid set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..formats import ArtifactError, parse_brief, parse_script, parse_storyboard
from ..models import Brief, Script, Storyboard
from ..settings import WorkspaceSettings
from ..state import Project, StageStatus, Workspace

_TODO = re.compile(r"\bTODO\b")


@dataclass
class CreativeReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    brief: Brief | None = None
    script: Script | None = None
    storyboard: Storyboard | None = None
    estimated_duration_s: float | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def estimate_duration(script: Script, settings: WorkspaceSettings) -> float:
    words = sum(s.word_count for s in script.scenes)
    return words / settings.narration_wpm * 60 + settings.scene_padding_s * len(script.scenes)


def _load(pdir: Path, name: str, parser, report: CreativeReport):
    path = pdir / name
    if not path.is_file():
        report.errors.append(f"{name}: missing")
        return None
    try:
        return parser(path.read_text(encoding="utf-8"))
    except ArtifactError as exc:
        report.errors += [f"{exc.filename}: {p}" for p in exc.problems]
        return None


def validate_creative(ws: Workspace, project: Project, settings: WorkspaceSettings, *, record: bool = True) -> CreativeReport:
    pdir = ws.dir(project.id)
    r = CreativeReport()
    r.brief = _load(pdir, "brief.md", parse_brief, r)
    r.script = _load(pdir, "script.md", parse_script, r)
    r.storyboard = _load(pdir, "storyboard.json", parse_storyboard, r)

    design_ok = True
    design = pdir / "design-system.yaml"
    try:
        yaml.safe_load(design.read_text(encoding="utf-8"))
    except FileNotFoundError:
        r.errors.append("design-system.yaml: missing")
        design_ok = False
    except yaml.YAMLError as exc:
        r.errors.append(f"design-system.yaml: invalid YAML: {exc}")
        design_ok = False

    for name in ("brief.md", "script.md", "storyboard.json"):
        path = pdir / name
        if path.is_file():
            hits = [n for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1) if _TODO.search(line)]
            if hits:
                shown = ", ".join(map(str, hits[:5])) + ("…" if len(hits) > 5 else "")
                r.errors.append(f"{name}: placeholder TODO text on line(s) {shown}")

    if r.script and r.storyboard:
        _cross_check_scenes(r.script, r.storyboard, r)
    if r.storyboard:
        for scene_id, asset in r.storyboard.asset_paths():
            p = (pdir / "assets" / asset).resolve()
            if not p.is_relative_to((pdir / "assets").resolve()):
                r.errors.append(f"storyboard.json: scene '{scene_id}' asset '{asset}' points outside assets/")
            elif not p.is_file():
                r.warnings.append(f"scene '{scene_id}': asset 'assets/{asset}' not found yet (required before build)")
    if r.script:
        r.estimated_duration_s = round(estimate_duration(r.script, settings), 1)
        target = project.settings.duration_s
        if abs(r.estimated_duration_s - target) > target * settings.duration_tolerance:
            r.warnings.append(
                f"estimated narration ≈{r.estimated_duration_s:.0f}s vs target {target}s "
                f"(±{settings.duration_tolerance:.0%}); adjust the script or the target"
            )
    if r.brief and r.brief.duration_s != project.settings.duration_s:
        r.warnings.append(f"brief says {r.brief.duration_s}s but the project target is {project.settings.duration_s}s")

    if record:
        _record(ws, project, r, design_ok)
    return r


def _cross_check_scenes(script: Script, sb: Storyboard, r: CreativeReport) -> None:
    s_ids = [s.id for s in script.scenes]
    b_ids = [s.id for s in sb.scenes]
    dupes = sorted({i for i in s_ids if s_ids.count(i) > 1})
    if dupes:
        r.errors.append(f"script.md: duplicate scene ids: {', '.join(dupes)}")
    only_script = [i for i in s_ids if i not in b_ids]
    only_board = [i for i in b_ids if i not in s_ids]
    if only_script:
        r.errors.append(f"scenes in script.md but not storyboard.json: {', '.join(only_script)}")
    if only_board:
        r.errors.append(f"scenes in storyboard.json but not script.md: {', '.join(only_board)}")
    if not (only_script or only_board or dupes) and s_ids != b_ids:
        r.errors.append(f"scene order differs: script {s_ids} vs storyboard {b_ids}")


def _record(ws: Workspace, project: Project, r: CreativeReport, design_ok: bool) -> None:
    def errs(prefix: str) -> str | None:
        mine = [e for e in r.errors if e.startswith(prefix)]
        return "; ".join(mine)[:500] if mine else None

    for stage, fname, obj in (
        ("brief", "brief.md", r.brief),
        ("script", "script.md", r.script),
        ("storyboard", "storyboard.json", r.storyboard),
    ):
        if obj is not None:
            # Parsed fine; cross-file problems mark the storyboard failed below.
            ws.mark_stage(project, stage, StageStatus.done, outputs=[fname], save=False)
        else:
            ws.mark_stage(project, stage, StageStatus.failed, error=errs(fname) or "missing", save=False)
    cross = [e for e in r.errors if e.startswith(("scenes in", "scene order", "storyboard.json: scene"))]
    if cross and r.storyboard is not None:
        ws.mark_stage(project, "storyboard", StageStatus.failed, outputs=["storyboard.json"], error="; ".join(cross)[:500], save=False)
    ws.mark_stage(
        project, "design", StageStatus.done if design_ok else StageStatus.failed,
        outputs=["design-system.yaml"] if design_ok else None,
        error=None if design_ok else errs("design-system.yaml"), save=False,
    )
    ws.save(project)
