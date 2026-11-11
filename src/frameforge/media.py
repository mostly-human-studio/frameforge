"""FFmpeg/FFprobe helpers: probing, validation and segment concatenation.

Every subprocess call passes an argument list (never a shell string), so paths
with spaces work on Windows.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from .errors import FrameForgeError


def tool(name: str) -> str:
    """Locate ffmpeg/ffprobe via FRAMEFORGE_FFMPEG_DIR or PATH."""
    custom = os.environ.get("FRAMEFORGE_FFMPEG_DIR")
    if custom:
        for candidate in (Path(custom) / name, Path(custom) / f"{name}.exe"):
            if candidate.is_file():
                return str(candidate)
    found = shutil.which(name)
    if not found:
        raise FrameForgeError(
            f"{name} not found.",
            hint="Install FFmpeg (Windows: 'winget install Gyan.FFmpeg') and make sure it is on PATH, "
                 "or set FRAMEFORGE_FFMPEG_DIR to the folder containing it.",
        )
    return found


def _run(args: list[str], what: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-8:])
        raise FrameForgeError(f"{what} failed (exit {proc.returncode}):\n{tail}", hint="See the FFmpeg output above.")
    return proc


@dataclass
class MediaInfo:
    path: Path
    duration_s: float
    video_codec: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    frames: int | None = None
    audio_codec: str | None = None
    audio_channels: int | None = None
    audio_sample_rate: int | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def has_video(self) -> bool:
        return self.video_codec is not None

    @property
    def has_audio(self) -> bool:
        return self.audio_codec is not None


def probe(path: Path) -> MediaInfo:
    path = Path(path)
    if not path.is_file():
        raise FrameForgeError(f"Media file not found: {path}", hint="Run 'frameforge build' to produce it.")
    proc = _run(
        [tool("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        f"ffprobe {path.name}",
    )
    data = json.loads(proc.stdout)
    info = MediaInfo(path=path, duration_s=float(data.get("format", {}).get("duration", 0.0)), raw=data)
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and info.video_codec is None:
            info.video_codec = s.get("codec_name")
            info.width, info.height = s.get("width"), s.get("height")
            rate = s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1"
            info.fps = float(Fraction(rate)) if rate != "0/0" else None
            if s.get("nb_frames", "").isdigit():
                info.frames = int(s["nb_frames"])
        elif s.get("codec_type") == "audio" and info.audio_codec is None:
            info.audio_codec = s.get("codec_name")
            info.audio_channels = s.get("channels")
            info.audio_sample_rate = int(s["sample_rate"]) if s.get("sample_rate") else None
    return info


@dataclass
class Expect:
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    frames: int | None = None
    duration_s: float | None = None
    duration_tolerance_s: float = 0.1
    video_codec: str | None = "h264"
    audio: bool | None = None  # True: must have audio; False: must not; None: don't care


def check(info: MediaInfo, expect: Expect) -> list[str]:
    """Return human-readable problems; empty list means the file meets expectations."""
    p: list[str] = []
    if not info.has_video:
        return [f"{info.path.name}: no video stream"]
    if expect.video_codec and info.video_codec != expect.video_codec:
        p.append(f"{info.path.name}: video codec {info.video_codec}, expected {expect.video_codec}")
    if expect.width and expect.height and (info.width, info.height) != (expect.width, expect.height):
        p.append(f"{info.path.name}: {info.width}x{info.height}, expected {expect.width}x{expect.height}")
    if expect.fps and info.fps and abs(info.fps - expect.fps) > 0.01:
        p.append(f"{info.path.name}: {info.fps:g} fps, expected {expect.fps:g}")
    if expect.frames is not None and info.frames is not None and info.frames != expect.frames:
        p.append(f"{info.path.name}: {info.frames} frames, expected {expect.frames}")
    if expect.duration_s is not None and abs(info.duration_s - expect.duration_s) > expect.duration_tolerance_s:
        p.append(f"{info.path.name}: {info.duration_s:.2f}s, expected {expect.duration_s:.2f}s ±{expect.duration_tolerance_s:g}")
    if expect.audio is True and not info.has_audio:
        p.append(f"{info.path.name}: no audio stream")
    if expect.audio is False and info.has_audio:
        p.append(f"{info.path.name}: unexpected audio stream")
    return p


def concat(segments: list[Path], output: Path) -> None:
    """Losslessly join same-format segments (FFmpeg concat demuxer, stream copy)."""
    if not segments:
        raise FrameForgeError("Nothing to concatenate.", hint="Render at least one scene first.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        listing = Path(td) / "segments.txt"
        lines = []
        for seg in segments:
            posix = Path(seg).resolve().as_posix().replace("'", r"'\''")
            lines.append(f"file '{posix}'")
        listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp_out = output.with_name(f".{output.stem}.tmp{output.suffix}")
        _run(
            [tool("ffmpeg"), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", "-movflags", "+faststart", str(tmp_out)],
            "concatenating scenes",
        )
        os.replace(tmp_out, output)


def extract_frame(video: Path, at_s: float, out_png: Path) -> None:
    _run([tool("ffmpeg"), "-v", "error", "-y", "-ss", f"{at_s:.3f}", "-i", str(video), "-frames:v", "1", str(out_png)],
         f"extracting frame at {at_s:.2f}s")


def frame_hashes(video: Path, times_s: list[float]) -> list[str]:
    """Hashes of decoded raw frames at given times. Byte-stable across container metadata differences."""
    import hashlib

    out = []
    for t in times_s:
        proc = subprocess.run(
            [tool("ffmpeg"), "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True,
        )
        if proc.returncode != 0:
            raise FrameForgeError(f"Could not decode frame at {t:.2f}s of {video.name}", hint="Is the file complete?")
        out.append(hashlib.sha256(proc.stdout).hexdigest())
    return out
