import shutil
from pathlib import Path

import pytest
import yaml

from frameforge.state import Workspace

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"

VALID_BRIEF = """---
title: Hello
audience: developers
objective: say hello
key_message: hello works
duration_s: 60
---
"""

VALID_SCRIPT = """# Hello

## s01 — Hook
Hello there. This is a short narrated scene.

## s02 — Point
Here is the point we want to make.
"""

VALID_STORYBOARD = """{
  "title": "Hello",
  "scenes": [
    {"id": "s01", "template": "title", "props": {"heading": "Hello"}},
    {"id": "s02", "template": "text-reveal", "props": {"heading": "Point", "bullets": ["one"]}}
  ]
}
"""


def set_settings(root: Path, **overrides) -> None:
    path = root / "config" / "settings.yaml"
    data = yaml.safe_load(path.read_text()) or {}
    data.update(overrides)
    path.write_text(yaml.safe_dump(data))


@pytest.fixture
def workspace(tmp_path, monkeypatch) -> Workspace:
    """An isolated workspace with the repo's config copied in.

    Uses the placeholder renderer (FFmpeg colour cards) at 1/8 scale, so
    pipeline tests run offline without Node or a browser.
    """
    shutil.copytree(REPO_ROOT / "config", tmp_path / "config")
    set_settings(tmp_path, renderer="placeholder", render_scale=0.125)
    monkeypatch.setenv("FRAMEFORGE_HOME", str(tmp_path))
    return Workspace(tmp_path)


def write_creative(ws: Workspace, pid: str) -> None:
    d = ws.dir(pid)
    (d / "brief.md").write_text(VALID_BRIEF, encoding="utf-8")
    (d / "script.md").write_text(VALID_SCRIPT, encoding="utf-8")
    (d / "storyboard.json").write_text(VALID_STORYBOARD, encoding="utf-8")
