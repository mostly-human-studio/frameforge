"""Placeholder renderer: solid colour cards via FFmpeg.

Exercises the whole pipeline (timing, caching, concat, validation) without a
browser or Node. Used by the test suite and for quick timing checks.
"""

from __future__ import annotations

import subprocess

from ..errors import FrameForgeError
from ..hashing import hash_data
from ..media import tool
from .base import RenderRequest

VERSION = "placeholder-v1"


class PlaceholderRenderer:
    name = "placeholder"

    def fingerprint(self) -> str:
        return hash_data(VERSION)

    def render(self, request: RenderRequest, on_event=None) -> None:
        ffmpeg = tool("ffmpeg")
        for job in request.jobs:
            size = job.props["size"]
            w = int(round(size["width"] * request.scale / 2)) * 2
            h = int(round(size["height"] * request.scale / 2)) * 2
            fps = job.props["timing"]["fps"]
            colour = "0x" + hash_data(job.props["scene"])[:6]
            job.output.parent.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run(
                [ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s={w}x{h}:r={fps}",
                 "-frames:v", str(job.frames), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                 "-fflags", "+bitexact", "-flags:v", "+bitexact", str(job.output)],
                capture_output=True, text=True,
            )
            if proc.returncode != 0:
                raise FrameForgeError(f"Placeholder render failed for {job.scene_id}: {proc.stderr[-400:]}", hint="Check FFmpeg.")
            if on_event:
                on_event({"event": "scene-done", "id": job.scene_id, "output": str(job.output), "frames": job.frames})
