"""Schemas for the creative artifacts.

Division of labour:
  * brief.md        why: audience, objective, key message, target duration
  * script.md       what is SAID, per scene (narration is the source of truth here)
  * storyboard.json what is SHOWN, per scene (template + props + assets)

Narration lives only in script.md so the two files can't disagree about
wording. They are joined by stable scene ids.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCENE_ID = r"^[a-z][a-z0-9-]{0,31}$"
ELEMENT_ID = r"^[A-Za-z][A-Za-z0-9_-]{0,31}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- brief

class Brief(_Strict):
    title: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    key_message: str = Field(min_length=1)
    duration_s: int = Field(ge=5, le=1800)
    tone: str = "clear, confident, friendly"
    notes: str = ""


# ---------------------------------------------------------------- design system
# Only what the renderer needs is required; extra keys (captions, logo…) pass through.

class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class FontSpec(_Open):
    family: str
    weight: int
    size_px: float


class Palette(_Open):
    background: str
    surface: str
    text: str
    muted: str
    accent: str
    zone_internal: str
    zone_external: str


class Typography(_Open):
    heading: FontSpec
    body: FontSpec
    mono: FontSpec


class LayoutSpec(_Open):
    safe_margin_px: float


class Transition(_Open):
    type: Literal["fade", "none"] = "fade"
    frames: int = Field(ge=0, le=120)


class Motion(_Open):
    scene_in: Transition
    scene_out: Transition
    element_stagger_frames: int = Field(ge=0, le=60)


class DesignSystem(_Open):
    name: str
    version: int | str
    palette: Palette
    typography: Typography
    layout: LayoutSpec
    motion: Motion


# ---------------------------------------------------------------- script

class ScriptScene(_Strict):
    id: str = Field(pattern=SCENE_ID)
    title: str = ""
    narration: str = Field(min_length=1)

    @property
    def word_count(self) -> int:
        return len(self.narration.split())


class Script(_Strict):
    title: str
    scenes: list[ScriptScene] = Field(min_length=1)


# ---------------------------------------------------------------- storyboard templates

class TitleProps(_Strict):
    heading: str = Field(min_length=1)
    subheading: str | None = None


class TextRevealProps(_Strict):
    heading: str = Field(min_length=1)
    bullets: list[str] = Field(min_length=1, max_length=6)


class Zone(_Strict):
    id: str = Field(pattern=ELEMENT_ID)
    label: str
    kind: Literal["internal", "external"]


class Node(_Strict):
    id: str = Field(pattern=ELEMENT_ID)
    label: str
    zone: str
    icon: str | None = None


class Edge(_Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    label: str | None = None
    style: Literal["request", "response", "stream"] = "request"


class DiagramProps(_Strict):
    heading: str | None = None
    zones: list[Zone] = Field(min_length=1, max_length=4)
    nodes: list[Node] = Field(min_length=1, max_length=10)
    edges: list[Edge] = Field(default_factory=list, max_length=12)  # list order = reveal order

    @model_validator(mode="after")
    def _references_resolve(self) -> "DiagramProps":
        zone_ids = [z.id for z in self.zones]
        node_ids = [n.id for n in self.nodes]
        _no_dupes("zone", zone_ids)
        _no_dupes("node", node_ids)
        for n in self.nodes:
            if n.zone not in zone_ids:
                raise ValueError(f"node '{n.id}' is in unknown zone '{n.zone}' (zones: {', '.join(zone_ids)})")
        for i, e in enumerate(self.edges):
            for end in (e.from_, e.to):
                if end not in node_ids:
                    raise ValueError(f"edge {i} references unknown node '{end}' (nodes: {', '.join(node_ids)})")
        return self


class ImageProps(_Strict):
    asset: str = Field(min_length=1, description="Path relative to the project's assets/ folder")
    caption: str | None = None
    fit: Literal["contain", "cover"] = "contain"


class _SceneBase(_Strict):
    id: str = Field(pattern=SCENE_ID)
    title: str = ""
    notes: str = ""


class TitleScene(_SceneBase):
    template: Literal["title"]
    props: TitleProps


class TextRevealScene(_SceneBase):
    template: Literal["text-reveal"]
    props: TextRevealProps


class DiagramScene(_SceneBase):
    template: Literal["architecture-diagram"]
    props: DiagramProps


class ImageScene(_SceneBase):
    template: Literal["image"]
    props: ImageProps


StoryboardScene = Annotated[
    Union[TitleScene, TextRevealScene, DiagramScene, ImageScene],
    Field(discriminator="template"),
]

TEMPLATES = ("title", "text-reveal", "architecture-diagram", "image")


class Storyboard(_Strict):
    version: Literal[1] = 1
    title: str
    scenes: list[StoryboardScene] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def _unique_ids(self) -> "Storyboard":
        _no_dupes("scene", [s.id for s in self.scenes])
        return self

    def asset_paths(self) -> list[tuple[str, str]]:
        """(scene id, asset path) for every asset the storyboard references."""
        return [(s.id, s.props.asset) for s in self.scenes if isinstance(s, ImageScene)]


def _no_dupes(kind: str, ids: list[str]) -> None:
    seen: set[str] = set()
    for i in ids:
        if i in seen:
            raise ValueError(f"duplicate {kind} id '{i}'")
        seen.add(i)
