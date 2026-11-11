import json

from conftest import EXAMPLES, write_creative
from frameforge.director import DraftRequest
from frameforge.director.stub import StubDirector
from frameforge.pipeline.creative import validate_creative
from frameforge.settings import load_settings
from frameforge.state import StageStatus

DEMO = (EXAMPLES / "llm-api-explainer.md").read_text(encoding="utf-8")


def _validate(ws, pid):
    return validate_creative(ws, ws.load(pid), load_settings(ws.root))


# ---------------------------------------------------------------- stub director

def test_stub_from_demo_source_maps_sections_to_templates():
    d = StubDirector().draft(DraftRequest("x", 60, DEMO))
    assert [s.id for s in d.script.scenes] == ["s01", "s02", "s03", "s04", "s05", "s06"]
    assert [s.template for s in d.storyboard.scenes] == [
        "title", "architecture-diagram", "text-reveal", "architecture-diagram", "architecture-diagram", "text-reveal"]
    assert d.brief.audience.startswith("Developers")
    s02 = d.storyboard.scenes[1].props
    assert {z.kind for z in s02.zones} == {"internal", "external"}


def test_stub_is_deterministic():
    a = StubDirector().draft(DraftRequest("x", 60, DEMO))
    b = StubDirector().draft(DraftRequest("x", 60, DEMO))
    assert a == b


def test_stub_narration_from_bullets_when_no_paragraphs():
    d = StubDirector().draft(DraftRequest("x", 60, "# T\n\n## Steps\n- First thing\n- Second thing\n"))
    assert d.script.scenes[1].narration == "Steps. First thing. Second thing."
    assert any("built from its bullets" in n for n in d.notes)


def test_stub_truncates_bullets_with_note():
    src = "# T\n\nIntro.\n\n## Many\nSay it.\n" + "".join(f"- b{i}\n" for i in range(9))
    d = StubDirector().draft(DraftRequest("x", 60, src))
    assert len(d.storyboard.scenes[1].props.bullets) == 6
    assert any("kept the first 6" in n for n in d.notes)


def test_stub_image_scene():
    d = StubDirector().draft(DraftRequest("x", 60, "# T\n\nIntro.\n\n## Pic\nLook.\n\n![The thing](assets/thing.png)\n"))
    assert d.storyboard.scenes[1].template == "image"
    assert d.storyboard.scenes[1].props.asset == "thing.png"


def test_stub_ignores_headings_inside_code_fences():
    src = "# T\n\nIntro.\n\n## Real\nText.\n\n```\n## not a scene\n```\n"
    d = StubDirector().draft(DraftRequest("x", 60, src))
    assert len(d.script.scenes) == 2


# ---------------------------------------------------------------- validation

def test_demo_validates_clean_within_duration(workspace):
    from frameforge.pipeline.plan import run_plan
    p = workspace.create("demo", project_id="demo")
    res = run_plan(workspace, p, load_settings(workspace.root), director="stub", source=EXAMPLES / "llm-api-explainer.md")
    assert res.report.ok, res.report.errors
    assert res.report.warnings == []
    assert 54 <= res.report.estimated_duration_s <= 66


def test_validation_records_stage_status(workspace):
    workspace.create("x", project_id="st")
    write_creative(workspace, "st")
    assert _validate(workspace, "st").ok
    p = workspace.load("st")
    for stage in ("brief", "script", "storyboard", "design"):
        assert p.stages[stage].status is StageStatus.done


def test_scene_mismatch_is_an_error(workspace):
    workspace.create("x", project_id="mm")
    write_creative(workspace, "mm")
    sb = workspace.dir("mm") / "storyboard.json"
    data = json.loads(sb.read_text())
    data["scenes"][1]["id"] = "s09"
    sb.write_text(json.dumps(data))
    r = _validate(workspace, "mm")
    assert "scenes in script.md but not storyboard.json: s02" in r.errors
    assert "scenes in storyboard.json but not script.md: s09" in r.errors
    assert workspace.load("mm").stages["storyboard"].status is StageStatus.failed


def test_scene_order_mismatch(workspace):
    workspace.create("x", project_id="ord")
    write_creative(workspace, "ord")
    sb = workspace.dir("ord") / "storyboard.json"
    data = json.loads(sb.read_text())
    data["scenes"].reverse()
    sb.write_text(json.dumps(data))
    assert any(e.startswith("scene order differs") for e in _validate(workspace, "ord").errors)


def test_todo_placeholders_block(workspace):
    workspace.create("x", project_id="todo")
    write_creative(workspace, "todo")
    (workspace.dir("todo") / "script.md").write_text("# T\n\n## s01 — A\nTODO: write this\n\n## s02 — B\nok\n")
    errs = _validate(workspace, "todo").errors
    assert any("script.md: placeholder TODO text on line(s) 4" in e for e in errs)


def test_missing_asset_warns_and_traversal_errors(workspace):
    workspace.create("x", project_id="img")
    write_creative(workspace, "img")
    sb = workspace.dir("img") / "storyboard.json"
    data = json.loads(sb.read_text())
    data["scenes"][1] = {"id": "s02", "template": "image", "props": {"asset": "missing.png"}}
    sb.write_text(json.dumps(data))
    r = _validate(workspace, "img")
    assert r.ok and any("assets/missing.png' not found" in w for w in r.warnings)

    data["scenes"][1]["props"]["asset"] = "../../secrets.png"
    sb.write_text(json.dumps(data))
    assert any("outside assets/" in e for e in _validate(workspace, "img").errors)


def test_duration_mismatch_warns(workspace):
    workspace.create("x", project_id="dur", duration_s=300)
    write_creative(workspace, "dur")
    w = _validate(workspace, "dur").warnings
    assert any("vs target 300s" in x for x in w)
    assert any("brief says 60s" in x for x in w)


# ---------------------------------------------------------------- scene blocks + morph

def test_scene_block_sets_template_exactly():
    src = ("# T\n\nIntro.\n\n## Outro\nBye now.\n\n"
           "```scene\ntemplate: morph\nprops:\n  from: FrameForge\n  to: Mostly Human Studio\n  tagline: Makers of FrameForge\n```\n")
    d = StubDirector().draft(DraftRequest("x", 60, src))
    s = d.storyboard.scenes[1]
    assert s.template == "morph" and s.props.from_ == "FrameForge" and s.props.to == "Mostly Human Studio"
    assert d.script.scenes[1].narration == "Bye now."


def test_scene_block_errors_name_the_section():
    import pytest
    from frameforge.errors import FrameForgeError
    src = "# T\n\nIntro.\n\n## Broken\nText.\n\n```scene\ntemplate: morph\nprops:\n  from: A\n```\n"
    with pytest.raises(FrameForgeError) as exc:
        StubDirector().draft(DraftRequest("x", 60, src))
    assert exc.value.message == "Scene block under '## Broken' is invalid: morph.props.to: Field required"


def test_morph_roundtrips_with_from_alias():
    from frameforge.formats import parse_storyboard, render_storyboard
    d = StubDirector().draft(DraftRequest("x", 60, (EXAMPLES / "frameforge-promo.md").read_text()))
    out = render_storyboard(d.storyboard)
    assert '"from": "FrameForge"' in out and "from_" not in out
    assert parse_storyboard(out) == d.storyboard
    assert [s.template for s in d.storyboard.scenes][-2:] == ["title", "morph"]


def test_promo_source_plans_clean(workspace):
    from frameforge.pipeline.plan import run_plan
    p = workspace.create("promo", project_id="promo", duration_s=56)
    res = run_plan(workspace, p, load_settings(workspace.root), director="stub", source=EXAMPLES / "frameforge-promo.md")
    assert res.report.ok, res.report.errors
    assert res.report.warnings == []


def test_design_background_defaults_to_plain():
    from frameforge.models import DesignSystem
    import yaml
    data = yaml.safe_load((EXAMPLES.parent / "config" / "profiles" / "technical-dark.yaml").read_text())
    assert DesignSystem.model_validate(data).background.style == "grid-glow"
    data.pop("background")
    assert DesignSystem.model_validate(data).background.style == "plain"
