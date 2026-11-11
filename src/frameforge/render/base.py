from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..errors import FrameForgeError
from ..settings import WorkspaceSettings

ASPECT_SIZES: dict[str, tuple[int, int]] = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}


def output_size(aspect: str, scale: float) -> tuple[int, int]:
    """Final pixel size after scaling; kept even for yuv420p."""
    w, h = ASPECT_SIZES[aspect]
    return (int(round(w * scale / 2)) * 2, int(round(h * scale / 2)) * 2)


@dataclass(frozen=True)
class SceneJob:
    scene_id: str
    props: dict          # full SceneProps for the renderer
    frames: int
    output: Path


@dataclass(frozen=True)
class RenderRequest:
    jobs: list[SceneJob]
    public_dir: Path | None      # project assets/ (served to image scenes)
    cache_dir: Path              # workspace-level render cache (bundles etc.)
    assets_key: str              # hash of public_dir contents; part of the bundle cache key
    scale: float = 1.0


class Renderer(Protocol):
    name: str

    def fingerprint(self) -> str:
        """Changes whenever renderer code changes, so cached segments are invalidated."""
        ...

    def render(self, request: RenderRequest, on_event=None) -> None: ...


def get_renderer(settings: WorkspaceSettings) -> Renderer:
    if settings.renderer == "remotion":
        from .remotion import RemotionRenderer

        return RemotionRenderer.from_settings(settings)
    if settings.renderer == "placeholder":
        from .placeholder import PlaceholderRenderer

        return PlaceholderRenderer()
    raise FrameForgeError(f"Unknown renderer '{settings.renderer}'.", hint="Use 'remotion' or 'placeholder' in config/settings.yaml.")
