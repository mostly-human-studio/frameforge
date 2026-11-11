"""FrameForge command-line interface."""

from __future__ import annotations

import functools
import json
from enum import Enum
from pathlib import Path
from typing import Callable

import typer

from . import __version__
from .errors import FrameForgeError, InvalidArtifact
from .models import Brief, Storyboard
from .paths import workspace_root
from .pipeline.creative import CreativeReport, validate_creative
from .pipeline.build import run_build
from .pipeline.plan import run_plan
from .render import get_renderer
from .settings import load_settings
from .state import STAGES, ApprovalGate, Workspace

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="FrameForge: turn a concept into a narrated MP4, with human approval gates.",
)


class DirectorChoice(str, Enum):
    stub = "stub"
    external = "external"


class SchemaChoice(str, Enum):
    brief = "brief"
    storyboard = "storyboard"


def _ws() -> Workspace:
    return Workspace(workspace_root())


def handle_errors(fn: Callable) -> Callable:
    """Turn FrameForgeError into a clean message, recovery hint and exit code."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except FrameForgeError as exc:
            typer.secho(f"Error: {exc.message}", fg=typer.colors.RED, err=True)
            if exc.hint:
                typer.echo(f"Hint: {exc.hint}", err=True)
            raise typer.Exit(exc.exit_code)

    return wrapper


def _print_report(r: CreativeReport) -> None:
    for e in r.errors:
        typer.secho(f"  ✗ {e}", fg=typer.colors.RED, err=True)
    for w in r.warnings:
        typer.secho(f"  ! {w}", fg=typer.colors.YELLOW, err=True)
    if r.script:
        est = f", ≈{r.estimated_duration_s:.0f}s narration" if r.estimated_duration_s is not None else ""
        typer.echo(f"  {len(r.script.scenes)} scenes{est}", err=True)
    if r.ok:
        typer.secho("  ✓ creative files valid", fg=typer.colors.GREEN, err=True)


def _require_valid(r: CreativeReport, project_id: str, action: str) -> None:
    if not r.ok:
        _print_report(r)
        raise InvalidArtifact(
            f"Cannot {action}: {len(r.errors)} problem(s) in the creative files.",
            hint=f"Fix them, then run 'frameforge validate {project_id}'.",
        )


@app.command()
def version() -> None:
    """Print the FrameForge version."""
    typer.echo(__version__)


@app.command()
@handle_errors
def create(
    concept: str = typer.Argument(..., help="What the video should explain."),
    duration: int | None = typer.Option(None, "--duration", min=5, max=1800, help="Target length in seconds."),
    profile: str | None = typer.Option(None, "--profile", help="Design profile under config/profiles/."),
    aspect: str | None = typer.Option(None, "--aspect", help="Aspect ratio: 16:9, 9:16 or 1:1."),
    project_id: str | None = typer.Option(None, "--id", help="Explicit project id (default: slug + random suffix)."),
) -> None:
    """Create a project and snapshot its design profile."""
    ws = _ws()
    s = load_settings(ws.root)
    aspect = aspect or s.default_aspect
    if aspect not in {"16:9", "9:16", "1:1"}:
        raise FrameForgeError(f"Unsupported aspect '{aspect}'.", hint="Use 16:9, 9:16 or 1:1.")
    project = ws.create(
        concept,
        duration_s=duration or s.default_duration_s,
        profile=profile or s.default_profile,
        aspect=aspect,
        fps=s.fps,
        project_id=project_id,
    )
    typer.echo(project.id)
    typer.echo(f"Created with profile {project.profile.name} v{project.profile.version}. Next: frameforge plan {project.id}", err=True)


@app.command("list")
@handle_errors
def list_projects() -> None:
    """List projects in the workspace."""
    for pid in _ws().list_ids():
        typer.echo(pid)


@app.command()
@handle_errors
def plan(
    project_id: str,
    source: Path | None = typer.Option(None, "--source", help="Markdown document to build the video from."),
    director: DirectorChoice | None = typer.Option(None, "--director", help="stub (offline) or external (Claude Code writes the files)."),
    force: bool = typer.Option(False, "--force", help="Replace existing creative files (backed up to history/ first)."),
) -> None:
    """Draft brief.md, script.md and storyboard.json for review."""
    ws = _ws()
    s = load_settings(ws.root)
    project = ws.load(project_id)
    result = run_plan(ws, project, s, director=(director.value if director else s.director), source=source, force=force)
    if result.backed_up_to:
        typer.echo(f"Backed up previous files to {result.backed_up_to.relative_to(ws.root)}", err=True)
    for n in result.notes:
        typer.echo(f"  · {n}", err=True)
    if result.director_brief:
        typer.echo(f"Director brief written: {result.director_brief.relative_to(ws.root)}")
        return
    _print_report(result.report)
    typer.echo(f"Review the files in projects/{project.id}/, then: frameforge approve {project.id} --stage creative", err=True)


@app.command()
@handle_errors
def validate(project_id: str) -> None:
    """Check the creative files and cross-check scene ids, templates and assets."""
    ws = _ws()
    project = ws.load(project_id)
    r = validate_creative(ws, project, load_settings(ws.root))
    _print_report(r)
    if not r.ok:
        raise typer.Exit(InvalidArtifact.exit_code)


@app.command()
def schema(which: SchemaChoice) -> None:
    """Print the JSON Schema for brief front matter or storyboard.json."""
    model = Brief if which is SchemaChoice.brief else Storyboard
    typer.echo(json.dumps(model.model_json_schema(by_alias=True), indent=2))


@app.command()
@handle_errors
def status(
    project_id: str,
    as_json: bool = typer.Option(False, "--json", help="Machine-readable output."),
) -> None:
    """Show stage progress and approval state for a project."""
    ws = _ws()
    project = ws.load(project_id)
    checks = {gate.value: ws.check_approval(project, gate) for gate in ApprovalGate}
    if as_json:
        payload = project.model_dump(mode="json")
        payload["approval_checks"] = {k: v.model_dump() for k, v in checks.items()}
        typer.echo(json.dumps(payload, indent=2))
        return
    typer.echo(f"{project.id}  —  {project.concept}")
    s = project.settings
    typer.echo(f"  {s.duration_s}s  {s.aspect}  {s.fps}fps  profile {project.profile.name} v{project.profile.version}")
    typer.echo("  stages:")
    for i, name in enumerate(STAGES, 1):
        st = project.stages[name]
        typer.echo(f"    {i:02d} {name:<11} {st.status.value}" + (f"  ({st.error})" if st.error else ""))
    typer.echo("  approvals:")
    for gate, check in checks.items():
        extra = f"  changed: {', '.join(check.changed)}" if check.changed else ""
        typer.echo(f"    {gate:<9} {check.state}{extra}")


@app.command()
@handle_errors
def approve(
    project_id: str,
    stage: ApprovalGate = typer.Option(..., "--stage", help="Which gate to approve."),
    note: str | None = typer.Option(None, "--note", help="Optional reviewer note."),
) -> None:
    """Record human approval, bound to the current content hashes."""
    ws = _ws()
    project = ws.load(project_id)
    if stage is ApprovalGate.creative:
        _require_valid(validate_creative(ws, project, load_settings(ws.root)), project.id, "approve")
    approval = ws.approve(project, stage, note=note)
    typer.echo(f"Approved '{stage.value}' for {project.id} ({len(approval.bound)} files bound).")


@app.command()
@handle_errors
def build(
    project_id: str,
    scene: str | None = typer.Option(None, "--scene", help="Render only this scene (preview); skips the final video."),
    force: bool = typer.Option(False, "--force", help="Re-render even when a cached segment matches."),
    scale: float | None = typer.Option(None, "--scale", min=0.1, max=1.0, help="Override render_scale, e.g. 0.5 for quick drafts."),
) -> None:
    """Render scenes and assemble output/final.mp4. Blocked until creative approval is valid."""
    ws = _ws()
    settings = load_settings(ws.root)
    if scale is not None:
        settings = settings.model_copy(update={"render_scale": scale})
    project = ws.load(project_id)
    renderer = get_renderer(settings)

    def on_event(e: dict) -> None:
        kind = e.get("event")
        if kind == "bundling":
            typer.echo("  bundling renderer (first run per renderer version)…", err=True)
        elif kind == "scene-done":
            typer.echo(f"  ✓ rendered {e['id']} ({e.get('frames')} frames)", err=True)

    result = run_build(ws, project, settings, renderer, only_scene=scene, force=force, on_event=on_event)
    if result.reused:
        typer.echo(f"  ↺ reused cached: {', '.join(result.reused)}", err=True)
    if result.final:
        w, h = result.size
        typer.echo(str(result.final.relative_to(ws.root)))
        typer.echo(f"Built {result.duration_s:.1f}s at {w}x{h} (silent until narration lands in M3).", err=True)
    else:
        seg = project.scenes.get(scene, {}).get("segment")
        typer.echo(f"projects/{project.id}/{seg}" if seg else "")


if __name__ == "__main__":
    app()
