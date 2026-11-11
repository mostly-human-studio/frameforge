"""Build stage: render each scene to a cached segment, then concatenate.

Each scene's cache key covers everything that affects its pixels: the scene
JSON, design system, frame count, fps, size, scale, renderer code, and (for
image scenes) the assets. If the key matches an existing segment, the scene
isn't rendered again. That gives scene-level invalidation for free (PLAN.md §2.3).

Until narration exists (M3), scene length is estimated from word count.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..errors import FrameForgeError
from ..hashing import hash_data, hash_file
from ..media import Expect, check, concat, probe
from ..models import Script, Storyboard
from ..render import RenderRequest, SceneJob, output_size
from ..render.base import ASPECT_SIZES, Renderer
from ..settings import WorkspaceSettings
from ..state import ApprovalGate, Project, StageStatus, Workspace
from .creative import validate_creative

FINAL = Path("output") / "final.mp4"


@dataclass
class SceneTiming:
    frames: int
    source: str  # "estimate" (M2) | "audio" (M3+)


@dataclass
class BuildReport:
    rendered: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    final: Path | None = None
    duration_s: float | None = None
    size: tuple[int, int] | None = None


def estimate_timings(script: Script, settings: WorkspaceSettings, fps: int) -> dict[str, SceneTiming]:
    out = {}
    for s in script.scenes:
        seconds = max(settings.min_scene_s, s.word_count / settings.narration_wpm * 60 + settings.scene_padding_s)
        out[s.id] = SceneTiming(frames=math.ceil(seconds * fps), source="estimate")
    return out


def assets_key(assets_dir: Path, storyboard: Storyboard) -> str:
    if not storyboard.asset_paths():
        return "none"
    files = {p.relative_to(assets_dir).as_posix(): hash_file(p) for p in sorted(assets_dir.rglob("*")) if p.is_file()}
    return hash_data(files)


def scene_props(scene_json: dict, design: dict, timing: SceneTiming, fps: int, aspect: str) -> dict:
    w, h = ASPECT_SIZES[aspect]
    return {
        "scene": scene_json,
        "design": design,
        "timing": {"fps": fps, "durationInFrames": timing.frames},
        "size": {"width": w, "height": h},
    }


def run_build(
    ws: Workspace,
    project: Project,
    settings: WorkspaceSettings,
    renderer: Renderer,
    *,
    only_scene: str | None = None,
    force: bool = False,
    on_event=None,
) -> BuildReport:
    ws.require_approval(project, ApprovalGate.creative)
    report = validate_creative(ws, project, settings)
    missing = [w for w in report.warnings if "required before build" in w]
    if report.errors or missing:
        from ..errors import InvalidArtifact

        problems = report.errors + missing
        raise InvalidArtifact(
            "Cannot build: " + "; ".join(problems[:5]) + (" …" if len(problems) > 5 else ""),
            hint=f"Fix the files (or add the assets), then run 'frameforge validate {project.id}'.",
        )
    assert report.script and report.storyboard

    pdir = ws.dir(project.id)
    fps = project.settings.fps
    aspect = project.settings.aspect
    design = yaml.safe_load((pdir / "design-system.yaml").read_text(encoding="utf-8"))
    design_hash = hash_data(design)
    timings = estimate_timings(report.script, settings, fps)
    akey = assets_key(pdir / "assets", report.storyboard)
    fingerprint = renderer.fingerprint()
    scale = settings.render_scale
    width, height = output_size(aspect, scale)

    scenes = report.storyboard.scenes
    if only_scene and only_scene not in {s.id for s in scenes}:
        raise FrameForgeError(f"No scene '{only_scene}' in storyboard.json.", hint="Scene ids: " + ", ".join(s.id for s in scenes))

    plan: list[tuple[str, str, Path, SceneJob | None]] = []  # (id, key, segment, job or None if cached)
    for sc in scenes:
        sj = sc.model_dump(mode="json", by_alias=True, exclude_none=True)
        t = timings[sc.id]
        key = hash_data({
            "scene": sj, "design": design_hash, "frames": t.frames, "fps": fps, "aspect": aspect,
            "scale": scale, "renderer": [renderer.name, fingerprint],
            "assets": akey if sc.template == "image" else None,
        })
        segment = pdir / "scenes" / f"{sc.id}.{key[:12]}.mp4"
        wanted = only_scene is None or sc.id == only_scene
        needs = wanted and (force or not segment.is_file())
        job = SceneJob(sc.id, scene_props(sj, design, t, fps, aspect), t.frames, segment) if needs else None
        plan.append((sc.id, key, segment, job))

    jobs = [j for *_, j in plan if j is not None]
    result = BuildReport(size=(width, height))
    try:
        renderer.render(
            RenderRequest(
                jobs=jobs,
                public_dir=pdir / "assets",
                cache_dir=ws.root / ".frameforge" / "cache",
                assets_key=akey,
                scale=scale,
            ),
            on_event=on_event,
        )
        for sid, key, segment, job in plan:
            if job is None:
                if only_scene is None or sid == only_scene:
                    result.reused.append(sid)
                continue
            problems = check(probe(segment), Expect(width=width, height=height, fps=fps, frames=job.frames, audio=False))
            if problems:
                raise FrameForgeError(f"Scene {sid} rendered incorrectly: " + "; ".join(problems), hint="Rerun with --force.")
            result.rendered.append(sid)
            project.scenes[sid] = {"key": key, "segment": segment.relative_to(pdir).as_posix(), "frames": job.frames,
                                   "timing": timings[sid].source}

        if only_scene is None:
            segments = [segment for _, _, segment, _ in plan]
            for sid, key, segment, _ in plan:
                project.scenes.setdefault(sid, {})
                project.scenes[sid].update({"key": key, "segment": segment.relative_to(pdir).as_posix(),
                                            "frames": timings[sid].frames, "timing": timings[sid].source})
            final = pdir / FINAL
            concat(segments, final)
            total_frames = sum(timings[s.id].frames for s in scenes)
            info = probe(final)
            problems = check(info, Expect(width=width, height=height, fps=fps, duration_s=total_frames / fps,
                                          duration_tolerance_s=max(0.1, 1.5 / fps), audio=False))
            if problems:
                raise FrameForgeError("Final video failed validation: " + "; ".join(problems), hint="Rerun with --force.")
            result.final, result.duration_s = final, info.duration_s
            _prune(pdir / "scenes", {segment.name for _, _, segment, _ in plan})
            project.scenes = {s.id: project.scenes[s.id] for s in scenes}
    except FrameForgeError as exc:
        ws.mark_stage(project, "build", StageStatus.failed, error=exc.message[:500])
        raise

    ws.mark_stage(project, "art", StageStatus.done, outputs=[f"assets/{a}" for _, a in report.storyboard.asset_paths()], save=False)
    if result.final:
        ws.mark_stage(project, "build", StageStatus.done, outputs=[FINAL.as_posix()], input_hash=hash_data([k for _, k, _, _ in plan]), save=False)
    ws.save(project)
    return result


def _prune(scenes_dir: Path, keep: set[str]) -> None:
    """Remove superseded segments: generated cache files only."""
    for p in scenes_dir.glob("*.mp4"):
        if p.name not in keep:
            p.unlink(missing_ok=True)
