"""Workspace settings from config/settings.yaml, with safe defaults."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from .errors import FrameForgeError
from .paths import config_dir


class WorkspaceSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    default_profile: str = "technical-dark"
    default_duration_s: int = 60
    default_aspect: str = "16:9"
    fps: int = 30
    scene_padding_s: float = 0.4
    duration_tolerance: float = 0.10
    narration_wpm: int = 150
    director: str = "stub"
    telemetry: bool = False
    min_scene_s: float = 3.0
    # Rendering
    renderer: str = "remotion"            # remotion | placeholder (colour cards via FFmpeg, no browser)
    render_scale: float = 1.0             # 0.5 renders 960x540 drafts from a 1920x1080 project
    render_concurrency: int | None = None
    crf: int = 18
    browser_executable: str | None = None  # env FRAMEFORGE_BROWSER overrides; None lets Remotion manage Chrome
    chrome_mode: str = "headless-shell"   # use "chrome-for-testing" with a regular Chrome install


def load_settings(root: Path | None = None) -> WorkspaceSettings:
    path = config_dir(root) / "settings.yaml"
    if not path.is_file():
        return WorkspaceSettings()
    try:
        return WorkspaceSettings(**(yaml.safe_load(path.read_text(encoding="utf-8")) or {}))
    except (yaml.YAMLError, ValidationError, TypeError) as exc:
        raise FrameForgeError(f"config/settings.yaml is invalid: {exc}", hint="Fix or delete it to use defaults.") from exc
