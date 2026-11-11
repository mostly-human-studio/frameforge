import shutil
import subprocess

import pytest

from frameforge.errors import FrameForgeError
from frameforge.media import Expect, check, concat, frame_hashes, probe

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def make_clip(path, frames=30, size="64x36", fps=30, colour="red", audio=False):
    args = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s={size}:r={fps}"]
    if audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000"]
    args += ["-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        args += ["-c:a", "aac", "-shortest"]
    subprocess.run(args + [str(path)], check=True)
    return path


def test_probe_reads_streams(tmp_path):
    info = probe(make_clip(tmp_path / "a.mp4", frames=45, audio=True))
    assert info.video_codec == "h264" and (info.width, info.height) == (64, 36)
    assert info.fps == 30 and info.frames == 45
    assert info.has_audio and info.audio_sample_rate == 48000
    assert abs(info.duration_s - 1.5) < 0.1


def test_check_reports_each_mismatch(tmp_path):
    info = probe(make_clip(tmp_path / "a.mp4", frames=30))
    problems = check(info, Expect(width=1920, height=1080, fps=25, frames=31, audio=True))
    text = " ".join(problems)
    assert "64x36, expected 1920x1080" in text
    assert "30 fps, expected 25" in text
    assert "30 frames, expected 31" in text
    assert "no audio stream" in text
    assert check(info, Expect(width=64, height=36, fps=30, frames=30, audio=False)) == []


def test_probe_missing_file_is_actionable(tmp_path):
    with pytest.raises(FrameForgeError) as exc:
        probe(tmp_path / "nope.mp4")
    assert exc.value.hint


def test_concat_joins_and_handles_awkward_paths(tmp_path):
    d = tmp_path / "with space's"
    d.mkdir()
    a = make_clip(d / "a.mp4", frames=30, colour="red")
    b = make_clip(d / "b.mp4", frames=15, colour="blue")
    out = tmp_path / "out" / "joined.mp4"
    concat([a, b], out)
    info = probe(out)
    assert info.frames == 45
    red, blue = frame_hashes(out, [0.5, 1.2])
    assert red != blue
