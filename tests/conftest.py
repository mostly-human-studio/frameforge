import shutil
from pathlib import Path

import pytest

from frameforge.state import Workspace

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path, monkeypatch) -> Workspace:
    """An isolated workspace with the repo's config copied in."""
    shutil.copytree(REPO_ROOT / "config", tmp_path / "config")
    monkeypatch.setenv("FRAMEFORGE_HOME", str(tmp_path))
    return Workspace(tmp_path)


def write_creative(ws: Workspace, pid: str) -> None:
    d = ws.dir(pid)
    (d / "brief.md").write_text("# Brief\nAudience: developers\n", encoding="utf-8")
    (d / "script.md").write_text("# Script\nScene 1: hello\n", encoding="utf-8")
    (d / "storyboard.json").write_text('{"scenes": [{"id": "s01"}]}', encoding="utf-8")
