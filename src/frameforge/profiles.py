"""Design profile loading and per-project snapshotting."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from .errors import FrameForgeError
from .hashing import hash_file
from .paths import config_dir


def profile_path(name: str, root: Path | None = None) -> Path:
    return config_dir(root) / "profiles" / f"{name}.yaml"


def available_profiles(root: Path | None = None) -> list[str]:
    d = config_dir(root) / "profiles"
    return sorted(p.stem for p in d.glob("*.yaml")) if d.is_dir() else []


def load_profile(name: str, root: Path | None = None) -> dict:
    path = profile_path(name, root)
    if not path.is_file():
        options = ", ".join(available_profiles(root)) or "none found"
        raise FrameForgeError(
            f"Design profile '{name}' not found at {path}.",
            hint=f"Available profiles: {options}. Add one under config/profiles/.",
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "version" not in data:
        raise FrameForgeError(
            f"Design profile '{name}' has no 'version' field.",
            hint="Add 'version: 1' so projects can record which profile version they used.",
        )
    return data


def snapshot_profile(name: str, dest: Path, root: Path | None = None) -> dict:
    """Copy a profile into a project. Returns {name, version, hash}."""
    data = load_profile(name, root)
    shutil.copyfile(profile_path(name, root), dest)
    return {"name": name, "version": data["version"], "hash": hash_file(dest)}
