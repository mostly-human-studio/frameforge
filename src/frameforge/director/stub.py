"""Offline, deterministic director.

Given a source Markdown document it produces a real draft:

    ---                          optional front matter → brief fields
    audience: Developers new to LLM APIs
    key_message: ...
    ---
    # Title                      → s01 title scene; intro paragraphs = its narration
    ## Section                   → one scene per H2
    Paragraphs                   → narration
    - bullets                    → text-reveal scene
    ```scene  (YAML)             → any template, exactly: {template: morph, props: {...}}
    ```diagram  (YAML)           → architecture-diagram scene
    ![caption](file.png)         → image scene (file under assets/)

Given only a concept, it produces a valid skeleton whose narration is
marked TODO. Validation refuses to approve TODO text, so a placeholder
can't be approved by accident.
"""

from __future__ import annotations

import re

import yaml
from pydantic import ValidationError

from ..errors import FrameForgeError
from ..formats import format_validation_error
from pydantic import TypeAdapter

from ..models import Brief, DiagramProps, Script, ScriptScene, Storyboard, StoryboardScene
from .base import Draft, DraftRequest

_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_FENCE = re.compile(r"^```(\w[\w-]*)?\s*\n(.*?)^```\s*$", re.S | re.M)
_IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)\s*$", re.M)
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")

MAX_BULLETS = 6
_SCENE = TypeAdapter(StoryboardScene)


class StubDirector:
    name = "stub"

    def draft(self, req: DraftRequest) -> Draft:
        if req.source_markdown and req.source_markdown.strip():
            return self._from_source(req)
        return self._skeleton(req)

    # ------------------------------------------------------------ from source

    def _from_source(self, req: DraftRequest) -> Draft:
        text = req.source_markdown.replace("\r\n", "\n")
        front: dict = {}
        if m := _FRONT.match(text):
            front = yaml.safe_load(m.group(1)) or {}
            text = text[m.end():]

        title, intro, sections = _split_sections(text)
        title = title or req.concept
        notes: list[str] = []

        script_scenes: list[ScriptScene] = []
        board_scenes: list[dict] = []

        intro_narr, _ = _narration_and_body(intro)
        script_scenes.append(ScriptScene(id="s01", title="Title", narration=intro_narr or f"{title}."))
        board_scenes.append({"id": "s01", "title": "Title", "template": "title",
                             "props": {"heading": title, "subheading": front.get("subtitle")}})

        for n, (heading, body) in enumerate(sections, start=2):
            sid = f"s{n:02d}"
            narration, visual = _narration_and_body(body)
            scene, note = _visual_scene(sid, heading, visual)
            if note:
                notes.append(note)
            if not narration:
                narration = _sentences([heading, *visual["bullets"]])
                notes.append(f"{sid}: no paragraphs under '{heading}', so narration was built from its bullets")
            script_scenes.append(ScriptScene(id=sid, title=heading, narration=narration))
            board_scenes.append(scene)

        words = sum(s.word_count for s in script_scenes)
        brief = Brief(
            title=title,
            audience=front.get("audience", "TODO: who is this for?"),
            objective=front.get("objective", f"Explain {title.rstrip('.').lower()}"),
            key_message=front.get("key_message", _first_sentence(intro_narr) or title),
            duration_s=int(front.get("duration_s", req.duration_s)),
            tone=front.get("tone", "clear, confident, friendly"),
            notes=f"Drafted offline by the stub director from a source document "
                  f"({len(script_scenes)} scenes, {words} narration words ≈ {words / req.wpm * 60:.0f}s).",
        )
        return Draft(brief=brief, script=Script(title=title, scenes=script_scenes),
                     storyboard=_storyboard(title, board_scenes), notes=tuple(notes))

    # ------------------------------------------------------------ skeleton

    def _skeleton(self, req: DraftRequest) -> Draft:
        concept = req.concept.strip()
        brief = Brief(
            title=concept,
            audience="TODO: who is this for?",
            objective=f"TODO: what should viewers be able to do after watching '{concept}'?",
            key_message="TODO: the one sentence viewers should remember",
            duration_s=req.duration_s,
            notes="Skeleton from the stub director. Replace every TODO, or rerun plan with "
                  "--source <doc.md>, or let Claude Code write these files (--director external).",
        )
        script = Script(title=concept, scenes=[
            ScriptScene(id="s01", title="Hook", narration=f"TODO: one or two sentences that open '{concept}'."),
            ScriptScene(id="s02", title="Key points", narration="TODO: walk through the main idea."),
            ScriptScene(id="s03", title="Recap", narration="TODO: restate the key message."),
        ])
        board = _storyboard(concept, [
            {"id": "s01", "title": "Hook", "template": "title", "props": {"heading": concept}},
            {"id": "s02", "title": "Key points", "template": "text-reveal",
             "props": {"heading": "Key points", "bullets": ["TODO: point one", "TODO: point two", "TODO: point three"]}},
            {"id": "s03", "title": "Recap", "template": "text-reveal",
             "props": {"heading": "Recap", "bullets": ["TODO: key message"]}},
        ])
        return Draft(brief=brief, script=script, storyboard=board,
                     notes=("Concept only: produced a TODO skeleton. Approval stays blocked until the TODOs are replaced.",))


# ---------------------------------------------------------------- helpers

def _split_sections(text: str) -> tuple[str, str, list[tuple[str, str]]]:
    """Return (H1 title, intro body, [(H2 heading, body), ...]), ignoring headings in code fences."""
    title, intro_lines, sections = "", [], []
    current: list[str] | None = None
    in_fence = False
    for line in text.split("\n"):
        if line.startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.startswith("# ") and not title and current is None:
            title = line[2:].strip()
            continue
        if not in_fence and line.startswith("## "):
            current = []
            sections.append((line[3:].strip(), current))
            continue
        (current if current is not None else intro_lines).append(line)
    return title, "\n".join(intro_lines), [(h, "\n".join(b)) for h, b in sections]


def _narration_and_body(body: str) -> tuple[str, dict]:
    visual = {"scene": None, "diagram": None, "image": None, "bullets": []}
    for m in _FENCE.finditer(body):
        lang = (m.group(1) or "").lower()
        if lang in ("diagram", "scene") and visual[lang] is None:
            visual[lang] = m.group(2)
    body = _FENCE.sub("", body)
    if m := _IMAGE.search(body):
        visual["image"] = (m.group(1), m.group(2))
    body = _IMAGE.sub("", body)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)

    paragraphs, para = [], []
    for line in body.split("\n"):
        if b := _BULLET.match(line):
            visual["bullets"].append(_strip_md(b.group(1)))
            continue
        if line.strip():
            para.append(line.strip())
        elif para:
            paragraphs.append(" ".join(para))
            para = []
    if para:
        paragraphs.append(" ".join(para))
    return "\n\n".join(_strip_md(p) for p in paragraphs), visual


def _visual_scene(sid: str, heading: str, v: dict) -> tuple[dict, str | None]:
    base = {"id": sid, "title": heading}
    if v["scene"] is not None:
        try:
            block = yaml.safe_load(v["scene"]) or {}
            if not isinstance(block, dict):
                raise ValueError("a ```scene block must be a YAML mapping with 'template' and 'props'")
            scene = {**base, **{k: block[k] for k in ("template", "props", "notes") if k in block}}
            _SCENE.validate_python(scene)
        except (yaml.YAMLError, ValidationError, ValueError) as exc:
            detail = "; ".join(format_validation_error(exc)) if isinstance(exc, ValidationError) else str(exc)
            raise FrameForgeError(
                f"Scene block under '## {heading}' is invalid: {detail}",
                hint="Run 'frameforge schema storyboard' for templates and their props.",
            ) from exc
        return scene, None
    if v["diagram"] is not None:
        try:
            props = yaml.safe_load(v["diagram"]) or {}
            props.setdefault("heading", heading)
            DiagramProps.model_validate(props)
        except (yaml.YAMLError, ValidationError) as exc:
            detail = "; ".join(format_validation_error(exc)) if isinstance(exc, ValidationError) else str(exc)
            raise FrameForgeError(
                f"Diagram under '## {heading}' is invalid: {detail}",
                hint="Fix the ```diagram block in the source document (see examples/).",
            ) from exc
        return {**base, "template": "architecture-diagram", "props": props}, None
    if v["image"] is not None:
        caption, path = v["image"]
        path = path.removeprefix("assets/")
        return {**base, "template": "image", "props": {"asset": path, "caption": caption or None}}, None
    if v["bullets"]:
        bullets = v["bullets"]
        note = None
        if len(bullets) > MAX_BULLETS:
            note = f"{sid}: '{heading}' has {len(bullets)} bullets; kept the first {MAX_BULLETS}"
            bullets = bullets[:MAX_BULLETS]
        return {**base, "template": "text-reveal", "props": {"heading": heading, "bullets": bullets}}, note
    return {**base, "template": "title", "props": {"heading": heading}}, None


def _storyboard(title: str, scenes: list[dict]) -> Storyboard:
    for s in scenes:
        s["props"] = {k: v for k, v in s["props"].items() if v is not None}
    return Storyboard.model_validate({"title": title, "scenes": scenes})


def _strip_md(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)    # links → text
    s = re.sub(r"(\*\*|__|\*|_|`)(.+?)\1", r"\2", s)  # emphasis / code
    return s.strip()


def _sentences(parts: list[str]) -> str:
    return " ".join(p if p.endswith((".", "!", "?")) else p + "." for p in parts if p)


def _first_sentence(text: str) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text.strip())
    return m.group(1) if m else text.strip()
