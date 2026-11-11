"""Real Remotion renders. Slow (tens of seconds); opt in with:

    FRAMEFORGE_TEST_REMOTION=1 pytest -m remotion

Needs Node, `npm ci` in renderer/, and a browser Remotion can use
(FRAMEFORGE_BROWSER + FRAMEFORGE_CHROME_MODE=chrome-for-testing for a regular Chrome).
"""

import os
import shutil

import pytest
from typer.testing import CliRunner

from conftest import EXAMPLES, REPO_ROOT, set_settings
from frameforge.cli import app
from frameforge.media import frame_hashes, probe

pytestmark = [
    pytest.mark.remotion,
    pytest.mark.skipif(os.environ.get("FRAMEFORGE_TEST_REMOTION") != "1", reason="set FRAMEFORGE_TEST_REMOTION=1"),
    pytest.mark.skipif(shutil.which("node") is None, reason="node not installed"),
    pytest.mark.skipif(not (REPO_ROOT / "renderer" / "node_modules").is_dir(), reason="run npm ci in renderer/"),
]
runner = CliRunner()


def run(*args):
    return runner.invoke(app, list(args))


@pytest.fixture
def remotion_ws(workspace):
    set_settings(workspace.root, renderer="remotion", render_scale=0.25)
    run("create", "LLM API explainer", "--id", "demo")
    run("plan", "demo", "--source", str(EXAMPLES / "llm-api-explainer.md"))
    assert run("approve", "demo", "--stage", "creative").exit_code == 0
    return workspace


def test_demo_renders_end_to_end(remotion_ws):
    r = run("build", "demo")
    assert r.exit_code == 0, r.output
    info = probe(remotion_ws.dir("demo") / "output" / "final.mp4")
    assert (info.width, info.height) == (480, 270)
    assert 54 <= info.duration_s <= 70


def test_rerender_is_frame_identical(remotion_ws):
    assert run("build", "demo", "--scene", "s02").exit_code == 0
    seg = next((remotion_ws.dir("demo") / "scenes").glob("s02.*.mp4"))
    times = [0.2, 1.5, probe(seg).duration_s - 0.5]
    first = frame_hashes(seg, times)
    assert run("build", "demo", "--scene", "s02", "--force").exit_code == 0
    assert frame_hashes(seg, times) == first
