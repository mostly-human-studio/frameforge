"""Build pipeline with the placeholder renderer: timing, caching, invalidation, validation."""

import json
import shutil

import pytest
from typer.testing import CliRunner

from conftest import EXAMPLES
from frameforge.cli import app
from frameforge.errors import FrameForgeError
from frameforge.media import probe
from frameforge.pipeline.build import run_build
from frameforge.render.placeholder import PlaceholderRenderer
from frameforge.settings import load_settings
from frameforge.state import StageStatus

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
runner = CliRunner()
DEMO = str(EXAMPLES / "llm-api-explainer.md")


def run(*args):
    return runner.invoke(app, list(args))


@pytest.fixture
def demo(workspace):
    """An approved demo project (approval is the human's step; done here only in tests)."""
    run("create", "LLM API explainer", "--id", "demo")
    run("plan", "demo", "--source", DEMO)
    assert run("approve", "demo", "--stage", "creative").exit_code == 0
    return workspace


def build(ws, **kw):
    return run_build(ws, ws.load("demo"), load_settings(ws.root), PlaceholderRenderer(), **kw)


def edit_storyboard(ws, fn):
    sb = ws.dir("demo") / "storyboard.json"
    data = json.loads(sb.read_text())
    fn(data)
    sb.write_text(json.dumps(data, indent=2))


def test_build_produces_validated_silent_mp4(demo):
    r = build(demo)
    assert r.rendered == ["s01", "s02", "s03", "s04", "s05", "s06"] and r.reused == []
    info = probe(r.final)
    assert (info.width, info.height) == (240, 136)  # 1920x1080 at 1/8, kept even
    assert info.fps == 30 and not info.has_audio
    p = demo.load("demo")
    assert abs(info.duration_s - sum(s["frames"] for s in p.scenes.values()) / 30) < 0.1
    assert p.stages["build"].status is StageStatus.done
    assert all(s["timing"] == "estimate" for s in p.scenes.values())


def test_rebuild_reuses_every_segment(demo):
    build(demo)
    r = build(demo)
    assert r.rendered == [] and len(r.reused) == 6


def test_storyboard_edit_rerenders_only_that_scene(demo):
    build(demo)
    before = dict(demo.load("demo").scenes)
    edit_storyboard(demo, lambda d: d["scenes"][2]["props"]["bullets"].append("Retries and timeouts"))
    run("approve", "demo", "--stage", "creative")  # human re-approval after an edit
    r = build(demo)
    assert r.rendered == ["s03"]
    after = demo.load("demo").scenes
    assert after["s03"]["key"] != before["s03"]["key"]
    assert all(after[s]["key"] == before[s]["key"] for s in before if s != "s03")
    segs = sorted(p.name for p in (demo.dir("demo") / "scenes").glob("*.mp4"))
    assert len(segs) == 6 and not any(before["s03"]["segment"].endswith(n) for n in segs)  # stale segment pruned


def test_narration_edit_changes_timing_of_that_scene_only(demo):
    build(demo)
    script = demo.dir("demo") / "script.md"
    script.write_text(script.read_text().replace(
        "The provider checks your key, applies rate limits, and runs the model.",
        "The provider checks your key, applies rate limits, queues the request, and runs the model on its own hardware."))
    run("approve", "demo", "--stage", "creative")
    assert build(demo).rendered == ["s04"]


def test_design_change_rerenders_everything(demo):
    build(demo)
    ds = demo.dir("demo") / "design-system.yaml"
    ds.write_text(ds.read_text().replace("#58A6FF", "#FF7B72"))
    run("approve", "demo", "--stage", "creative")
    assert len(build(demo).rendered) == 6


def test_unapproved_edit_blocks_build(demo):
    build(demo)
    edit_storyboard(demo, lambda d: d["scenes"][0]["props"].update(heading="New title"))
    with pytest.raises(FrameForgeError, match="stale"):
        build(demo)


def test_single_scene_preview(demo):
    r = build(demo, only_scene="s02")
    assert r.rendered == ["s02"] and r.final is None
    assert not (demo.dir("demo") / "output" / "final.mp4").exists()
    r = build(demo)
    assert "s02" in r.reused and len(r.rendered) == 5


def test_unknown_scene(demo):
    with pytest.raises(FrameForgeError, match="No scene 's99'"):
        build(demo, only_scene="s99")


def test_force_rerenders(demo):
    build(demo)
    assert len(build(demo, force=True).rendered) == 6


def test_renderer_failure_marks_stage_failed(demo):
    class Broken(PlaceholderRenderer):
        def render(self, request, on_event=None):
            raise FrameForgeError("boom", hint="test")

    with pytest.raises(FrameForgeError, match="boom"):
        run_build(demo, demo.load("demo"), load_settings(demo.root), Broken())
    st = demo.load("demo").stages["build"]
    assert st.status is StageStatus.failed and st.error == "boom"


def test_bad_render_output_is_caught(demo):
    class WrongSize(PlaceholderRenderer):
        def render(self, request, on_event=None):
            super().render(request.__class__(**{**request.__dict__, "scale": request.scale * 2}), on_event)

    with pytest.raises(FrameForgeError, match="rendered incorrectly"):
        run_build(demo, demo.load("demo"), load_settings(demo.root), WrongSize())


def test_cli_build_and_scale_override(demo):
    r = run("build", "demo", "--scale", "0.25")
    assert r.exit_code == 0, r.output
    assert "Built" in r.stderr and "480x270" in r.stderr
    assert r.stdout.strip().endswith("final.mp4")


def test_missing_image_asset_blocks_build(demo):
    edit_storyboard(demo, lambda d: d["scenes"].__setitem__(2, {"id": "s03", "template": "image", "props": {"asset": "shot.png"}}))
    run("approve", "demo", "--stage", "creative")
    r = run("build", "demo")
    assert r.exit_code == 6 and "shot.png" in r.stderr


def test_invalid_design_system_reported(demo):
    ds = demo.dir("demo") / "design-system.yaml"
    ds.write_text(ds.read_text().replace("accent:", "accnt:"))
    r = run("validate", "demo")
    assert r.exit_code == 6 and "palette.accent" in r.stderr
