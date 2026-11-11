"""Read and write the human-editable creative files.

brief.md   YAML front matter (structured fields) + free-form notes body.
script.md  `# Title`, then one `## <scene-id> — <scene title>` section per scene.
           Section body is narration. HTML comments are ignored, so
           `<!-- direction: slow down here -->` never gets spoken.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import Brief, Script, ScriptScene, Storyboard

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)(.*)\Z", re.S)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_SCENE_HEADING = re.compile(r"^##\s+([^\s:—–·|]+)\s*(?:[—–:·|-]+\s*)?(.*?)\s*$")


class ArtifactError(Exception):
    """A creative file failed to parse or validate. `problems` are human-readable."""

    def __init__(self, filename: str, problems: list[str]):
        super().__init__(f"{filename}: " + "; ".join(problems))
        self.filename = filename
        self.problems = problems


def format_validation_error(exc: ValidationError) -> list[str]:
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p not in ("function-after",))
        msg = err["msg"].removeprefix("Value error, ")
        out.append(f"{loc}: {msg}" if loc else msg)
    return out


# ------------------------------------------------------------------ brief

def render_brief(brief: Brief) -> str:
    fields = brief.model_dump(exclude={"notes"})
    fm = yaml.safe_dump(fields, sort_keys=False, allow_unicode=True, width=100).strip()
    body = brief.notes.strip()
    return f"---\n{fm}\n---\n\n{body}\n" if body else f"---\n{fm}\n---\n"


def parse_brief(text: str) -> Brief:
    m = _FRONT_MATTER.match(text.replace("\r\n", "\n"))
    if not m:
        raise ArtifactError("brief.md", ["missing YAML front matter between '---' lines at the top"])
    try:
        fields = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ArtifactError("brief.md", [f"front matter is not valid YAML: {exc}"]) from exc
    if not isinstance(fields, dict):
        raise ArtifactError("brief.md", ["front matter must be a mapping of field: value"])
    try:
        return Brief(**fields, notes=m.group(2).strip())
    except ValidationError as exc:
        raise ArtifactError("brief.md", format_validation_error(exc)) from exc
    except TypeError as exc:  # e.g. 'notes' given twice
        raise ArtifactError("brief.md", [str(exc)]) from exc


# ------------------------------------------------------------------ script

def render_script(script: Script) -> str:
    parts = [f"# {script.title}", ""]
    for s in script.scenes:
        heading = f"## {s.id} — {s.title}" if s.title else f"## {s.id}"
        parts += [heading, "", s.narration.strip(), ""]
    return "\n".join(parts)


def parse_script(text: str) -> Script:
    text = _COMMENT.sub("", text.replace("\r\n", "\n"))
    title = ""
    scenes: list[dict] = []
    current: dict | None = None
    problems: list[str] = []

    for lineno, line in enumerate(text.split("\n"), 1):
        if line.startswith("## "):
            m = _SCENE_HEADING.match(line)
            current = {"id": m.group(1), "title": m.group(2), "lines": [], "line": lineno}
            scenes.append(current)
        elif line.startswith("# ") and not title and current is None:
            title = line[2:].strip()
        elif current is not None:
            current["lines"].append(line)
        elif line.strip():
            problems.append(f"line {lineno}: text before the first '## <scene-id>' heading is ignored")

    if not scenes:
        raise ArtifactError("script.md", ["no scenes found; add sections like '## s01 — Hook'"])

    parsed: list[ScriptScene] = []
    for sc in scenes:
        paragraphs = [" ".join(p.split()) for p in "\n".join(sc["lines"]).split("\n\n")]
        narration = "\n\n".join(p for p in paragraphs if p)
        try:
            parsed.append(ScriptScene(id=sc["id"], title=sc["title"], narration=narration))
        except ValidationError as exc:
            for p in format_validation_error(exc):
                problems.append(f"line {sc['line']} ({sc['id']}): {p}")
    hard = [p for p in problems if "is ignored" not in p]
    if hard:
        raise ArtifactError("script.md", hard)
    return Script(title=title or "Untitled", scenes=parsed)


# ------------------------------------------------------------------ storyboard

def render_storyboard(sb: Storyboard) -> str:
    return json.dumps(sb.model_dump(mode="json", by_alias=True, exclude_none=True), indent=2, ensure_ascii=False) + "\n"


def parse_storyboard(text: str) -> Storyboard:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ArtifactError("storyboard.json", [f"invalid JSON at line {exc.lineno} col {exc.colno}: {exc.msg}"]) from exc
    try:
        return Storyboard.model_validate(data)
    except ValidationError as exc:
        raise ArtifactError("storyboard.json", format_validation_error(exc)) from exc


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")
