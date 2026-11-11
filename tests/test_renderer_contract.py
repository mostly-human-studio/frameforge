"""Guards on the Python ↔ Remotion contract that don't need Node or a browser."""

import re
import shutil

import pytest

from conftest import REPO_ROOT
from frameforge.errors import FrameForgeError
from frameforge.models import TEMPLATES
from frameforge.pipeline.build import SceneTiming, scene_props
from frameforge.render.base import output_size
from frameforge.render.remotion import RemotionRenderer

RENDERER = REPO_ROOT / "renderer"


def test_never_passes_a_remotion_license_key():
    """Remotion sends a usage event to remotion.pro whenever licenseKey is set
    (including 'free-license'). AT8: no telemetry by default, so we never set it."""
    code = (RENDERER / "scripts" / "render-scenes.mjs").read_text()
    code_without_comments = re.sub(r"//.*", "", code)
    assert "licenseKey" not in code_without_comments
    assert "apiKey" not in code_without_comments


def test_renders_to_partial_then_renames():
    code = (RENDERER / "scripts" / "render-scenes.mjs").read_text()
    assert ".partial.mp4" in code and "outputLocation: partial" in code and "renameSync(partial, scene.output)" in code


def test_every_template_is_handled_by_the_renderer():
    scene_tsx = (RENDERER / "src" / "Scene.tsx").read_text()
    handled = set(re.findall(r"case '([a-z-]+)':", scene_tsx))
    assert handled == set(TEMPLATES)


def test_props_shape_matches_typescript_contract():
    props = scene_props({"id": "s01", "template": "title", "props": {"heading": "Hi"}}, {"name": "x"}, SceneTiming(90, "estimate"), 30, "9:16")
    assert set(props) == {"scene", "design", "timing", "size"}
    assert props["timing"] == {"fps": 30, "durationInFrames": 90}
    assert props["size"] == {"width": 1080, "height": 1920}
    types_ts = (RENDERER / "src" / "types.ts").read_text()
    for key in ("scene: SceneSpec", "design: Design", "durationInFrames", "size: {width: number; height: number}"):
        assert key in types_ts


@pytest.mark.parametrize("aspect, scale, expected", [("16:9", 1, (1920, 1080)), ("16:9", 0.125, (240, 136)), ("9:16", 0.5, (540, 960))])
def test_output_size_even(aspect, scale, expected):
    assert output_size(aspect, scale) == expected


def test_fingerprint_tracks_renderer_source(tmp_path):
    shutil.copytree(RENDERER / "src", tmp_path / "src")
    r = RemotionRenderer(tmp_path)
    before = r.fingerprint()
    (tmp_path / "src" / "theme.ts").write_text((tmp_path / "src" / "theme.ts").read_text() + "\n// tweak\n")
    assert r.fingerprint() != before


def test_missing_dependencies_are_actionable(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "render-scenes.mjs").write_text("")
    with pytest.raises(FrameForgeError) as exc:
        RemotionRenderer(tmp_path)._script()
    assert "npm ci" in exc.value.hint


def test_bad_browser_path_is_actionable(tmp_path):
    if not (RENDERER / "node_modules").is_dir():
        pytest.skip("renderer deps not installed")
    with pytest.raises(FrameForgeError, match="Browser not found"):
        RemotionRenderer(RENDERER, browser_executable=str(tmp_path / "chrome.exe"))._script()
