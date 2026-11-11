"""`frameforge plan`: draft the creative files without ever clobbering human edits."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..director import DraftRequest, get_director
from ..errors import FrameForgeError
from ..formats import render_brief, render_script, render_storyboard, write_text
from ..models import Brief, Storyboard
from ..settings import WorkspaceSettings
from ..state import Project, Workspace
from .creative import CreativeReport, validate_creative

DRAFTED = ("brief.md", "script.md", "storyboard.json")


@dataclass
class PlanResult:
    report: CreativeReport | None
    notes: list[str] = field(default_factory=list)
    backed_up_to: Path | None = None
    director_brief: Path | None = None


def run_plan(
    ws: Workspace,
    project: Project,
    settings: WorkspaceSettings,
    *,
    director: str,
    source: Path | None = None,
    force: bool = False,
) -> PlanResult:
    pdir = ws.dir(project.id)
    existing = [n for n in DRAFTED if (pdir / n).exists()]
    if existing and not force:
        raise FrameForgeError(
            f"Creative files already exist: {', '.join(existing)}.",
            hint=f"Edit them and run 'frameforge validate {project.id}', or rerun plan with --force "
                 "(current files are backed up to history/ first).",
        )

    source_text = None
    if source is not None:
        source = Path(source)
        if not source.is_file():
            raise FrameForgeError(f"Source document not found: {source}", hint="Pass a path to a Markdown file.")
        source_text = source.read_text(encoding="utf-8")

    result = PlanResult(report=None)
    if existing:
        result.backed_up_to = _backup(pdir, existing)

    if source_text is not None:
        write_text(pdir / "source.md", source_text)  # keep the project self-contained

    if director == "external":
        result.director_brief = _write_director_brief(pdir, project, settings, has_source=source_text is not None)
        result.notes.append("No files drafted. Claude Code (or you) writes them, then runs 'frameforge validate'.")
        return result

    draft = get_director(director).draft(
        DraftRequest(concept=project.concept, duration_s=project.settings.duration_s,
                     source_markdown=source_text, wpm=settings.narration_wpm)
    )
    write_text(pdir / "brief.md", render_brief(draft.brief))
    write_text(pdir / "script.md", render_script(draft.script))
    write_text(pdir / "storyboard.json", render_storyboard(draft.storyboard))
    result.notes += list(draft.notes)
    result.report = validate_creative(ws, project, settings)
    return result


def _backup(pdir: Path, names: list[str]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = pdir / "history" / stamp
    dest.mkdir(parents=True)
    for n in names:
        shutil.copy2(pdir / n, dest / n)
    return dest


def _write_director_brief(pdir: Path, project: Project, settings: WorkspaceSettings, *, has_source: bool) -> Path:
    schema_dir = pdir / "schemas"
    schema_dir.mkdir(exist_ok=True)
    write_text(schema_dir / "brief.schema.json", json.dumps(Brief.model_json_schema(), indent=2))
    write_text(schema_dir / "storyboard.schema.json", json.dumps(Storyboard.model_json_schema(by_alias=True), indent=2))
    words = int(project.settings.duration_s / 60 * settings.narration_wpm)
    src = "Source material is in `source.md`. Stay faithful to it.\n" if has_source else ""
    text = f"""# Director brief: {project.id}

You are drafting the creative files for a FrameForge video. A human approves them; you never do.

**Concept:** {project.concept}
**Target:** {project.settings.duration_s}s ≈ {words} narration words at {settings.narration_wpm} wpm · {project.settings.aspect}
**Design profile:** `design-system.yaml` ({project.profile.name} v{project.profile.version})
{src}
## Write these files in this folder

1. `brief.md`: YAML front matter matching `schemas/brief.schema.json` (title, audience, objective,
   key_message, duration_s, tone), then free-form notes.
2. `script.md`: `# Title`, then one `## <scene-id> — <Scene title>` section per scene. The body is
   spoken narration only. Use `<!-- comments -->` for direction; they are never spoken.
3. `storyboard.json`: matches `schemas/storyboard.schema.json`. Same scene ids, same order as the
   script. Templates: `title`, `text-reveal` (≤6 bullets), `architecture-diagram` (zones are
   `internal` for the viewer's own app/backend and `external` for third-party services; edges reveal in
   list order), `image` (file under `assets/`).

## Rules
- Scene ids look like `s01`, `s02`… and never change once written. Insert new scenes with new ids (e.g. `s02b`).
- No TODO text: validation blocks approval while any remains.
- When done, run `frameforge validate {project.id}` and fix every error. Warnings are judgment calls.
- Do not run `frameforge approve`.
"""
    path = pdir / "DIRECTOR.md"
    write_text(path, text)
    return path
