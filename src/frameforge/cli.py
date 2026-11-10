"""FrameForge command-line interface."""

from __future__ import annotations

import functools
import json
from typing import Callable

import typer

from . import __version__
from .errors import FrameForgeError
from .paths import workspace_root
from .state import STAGES, ApprovalGate, Workspace

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="FrameForge: turn a concept into a narrated MP4, with human approval gates.",
)


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


@app.command()
def version() -> None:
    """Print the FrameForge version."""
    typer.echo(__version__)


@app.command()
@handle_errors
def create(
    concept: str = typer.Argument(..., help="What the video should explain."),
    duration: int = typer.Option(60, "--duration", min=5, max=1800, help="Target length in seconds."),
    profile: str = typer.Option("technical-dark", "--profile", help="Design profile under config/profiles/."),
    aspect: str = typer.Option("16:9", "--aspect", help="Aspect ratio: 16:9, 9:16 or 1:1."),
    project_id: str | None = typer.Option(None, "--id", help="Explicit project id (default: slug + random suffix)."),
) -> None:
    """Create a project and snapshot its design profile."""
    if aspect not in {"16:9", "9:16", "1:1"}:
        raise FrameForgeError(f"Unsupported aspect '{aspect}'.", hint="Use 16:9, 9:16 or 1:1.")
    project = _ws().create(concept, duration_s=duration, profile=profile, aspect=aspect, project_id=project_id)
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
    approval = ws.approve(project, stage, note=note)
    typer.echo(f"Approved '{stage.value}' for {project.id} ({len(approval.bound)} files bound).")


@app.command()
@handle_errors
def build(project_id: str) -> None:
    """Render the video. Blocked until creative approval is valid."""
    ws = _ws()
    project = ws.load(project_id)
    ws.require_approval(project, ApprovalGate.creative)
    raise FrameForgeError(
        "Rendering is not implemented yet (milestone M2).",
        hint="Creative approval is valid; the gate is working. See PLAN.md §3.",
    )


if __name__ == "__main__":
    app()
