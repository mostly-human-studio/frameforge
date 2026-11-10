"""Workspace and project path resolution."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_SUBDIRS = ("assets", "audio", "scenes", "review", "output")

# Files whose hashes a creative approval binds to (relative to project dir).
CREATIVE_ARTIFACTS = ("brief.md", "script.md", "storyboard.json", "design-system.yaml")


def workspace_root() -> Path:
    """FRAMEFORGE_HOME if set, else the current directory."""
    env = os.environ.get("FRAMEFORGE_HOME")
    return Path(env).expanduser().resolve() if env else Path.cwd().resolve()


def projects_dir(root: Path | None = None) -> Path:
    return (root or workspace_root()) / "projects"


def config_dir(root: Path | None = None) -> Path:
    return (root or workspace_root()) / "config"


def project_dir(project_id: str, root: Path | None = None) -> Path:
    return projects_dir(root) / project_id
