from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..errors import FrameForgeError
from ..models import Brief, Script, Storyboard


@dataclass(frozen=True)
class DraftRequest:
    concept: str
    duration_s: int
    source_markdown: str | None = None
    wpm: int = 150


@dataclass(frozen=True)
class Draft:
    brief: Brief
    script: Script
    storyboard: Storyboard
    notes: tuple[str, ...] = ()


class Director(Protocol):
    name: str

    def draft(self, request: DraftRequest) -> Draft: ...


def get_director(name: str) -> Director:
    if name == "stub":
        from .stub import StubDirector

        return StubDirector()
    raise FrameForgeError(
        f"Unknown director '{name}'.",
        hint="Use 'stub' (offline), or 'external' to have Claude Code write the files.",
    )
