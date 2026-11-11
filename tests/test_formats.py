import json

import pytest

from conftest import VALID_STORYBOARD
from frameforge.formats import (
    ArtifactError, parse_brief, parse_script, parse_storyboard, render_brief, render_script, render_storyboard,
)
from frameforge.models import Brief


def test_brief_roundtrip():
    b = Brief(title="T", audience="devs", objective="o", key_message="k", duration_s=45, notes="Some notes.")
    assert parse_brief(render_brief(b)) == b


def test_brief_without_front_matter():
    with pytest.raises(ArtifactError, match="front matter"):
        parse_brief("# just markdown")


def test_brief_field_errors_are_named():
    with pytest.raises(ArtifactError) as exc:
        parse_brief("---\ntitle: T\naudience: a\nobjective: o\nkey_message: k\nduration_s: 2\n---\n")
    assert any(p.startswith("duration_s") for p in exc.value.problems)


def test_brief_rejects_unknown_fields():
    with pytest.raises(ArtifactError, match="mood: Extra inputs"):
        parse_brief("---\ntitle: T\naudience: a\nobjective: o\nkey_message: k\nduration_s: 60\nmood: x\n---\n")


def test_script_parses_separators_comments_and_paragraphs():
    s = parse_script(
        "# Title\n\n## s01 — Hook\nLine one\ncontinues.\n\nSecond para. <!-- slow down -->\n\n"
        "## s02: Middle\nMid.\n\n## s03 - End\nEnd.\n\n## s04\nNo title.\n"
    )
    assert [x.id for x in s.scenes] == ["s01", "s02", "s03", "s04"]
    assert [x.title for x in s.scenes] == ["Hook", "Middle", "End", ""]
    assert s.scenes[0].narration == "Line one continues.\n\nSecond para."
    assert "slow down" not in s.scenes[0].narration


def test_script_roundtrip():
    s = parse_script("# T\n\n## s01 — A\nHello.\n\n## s02 — B\nWorld.\n")
    assert parse_script(render_script(s)) == s


def test_script_windows_line_endings():
    s = parse_script("# T\r\n\r\n## s01 — A\r\nHello.\r\n")
    assert s.scenes[0].narration == "Hello."


def test_script_empty_narration_reports_line():
    with pytest.raises(ArtifactError) as exc:
        parse_script("# T\n\n## s01 — A\n\n## s02 — B\nok\n")
    assert "line 3 (s01)" in exc.value.problems[0]


def test_script_bad_scene_id():
    with pytest.raises(ArtifactError, match="s 1|pattern"):
        parse_script("# T\n\n## S01 — A\ntext\n")


def test_storyboard_roundtrip_keeps_from_alias():
    data = json.loads(VALID_STORYBOARD)
    data["scenes"].append({
        "id": "s03", "template": "architecture-diagram",
        "props": {"zones": [{"id": "z", "label": "Z", "kind": "internal"}],
                  "nodes": [{"id": "a", "label": "A", "zone": "z"}, {"id": "b", "label": "B", "zone": "z"}],
                  "edges": [{"from": "a", "to": "b"}]},
    })
    sb = parse_storyboard(json.dumps(data))
    out = render_storyboard(sb)
    assert '"from": "a"' in out and "from_" not in out
    assert parse_storyboard(out) == sb


@pytest.mark.parametrize("mutate, expect", [
    (lambda d: d["scenes"].append(dict(d["scenes"][0])), "duplicate scene id 's01'"),
    (lambda d: d["scenes"][0].update(template="hologram"), "template"),
    (lambda d: d["scenes"][1]["props"].update(bullets=list("abcdefg")), "at most 6"),
    (lambda d: d["scenes"][0]["props"].update(colour="red"), "Extra inputs"),
])
def test_storyboard_rejections(mutate, expect):
    data = json.loads(VALID_STORYBOARD)
    mutate(data)
    with pytest.raises(ArtifactError) as exc:
        parse_storyboard(json.dumps(data))
    assert expect in " ".join(exc.value.problems)


def test_diagram_dangling_edge_named():
    data = {"title": "T", "scenes": [{"id": "s01", "template": "architecture-diagram", "props": {
        "zones": [{"id": "z", "label": "Z", "kind": "external"}],
        "nodes": [{"id": "a", "label": "A", "zone": "z"}],
        "edges": [{"from": "a", "to": "ghost"}]}}]}
    with pytest.raises(ArtifactError) as exc:
        parse_storyboard(json.dumps(data))
    assert "unknown node 'ghost'" in " ".join(exc.value.problems)


def test_storyboard_invalid_json_location():
    with pytest.raises(ArtifactError, match="line 1"):
        parse_storyboard("{nope")
