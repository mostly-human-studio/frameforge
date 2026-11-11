"""Remotion renderer adapter: runs renderer/scripts/render-scenes.mjs with Node."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..errors import FrameForgeError
from ..hashing import hash_data, hash_file
from ..settings import WorkspaceSettings
from .base import RenderRequest

REPO_RENDERER_DIR = Path(__file__).resolve().parents[3] / "renderer"
_FINGERPRINT_GLOBS = ("src/**/*", "scripts/**/*", "package-lock.json")


class RemotionRenderer:
    name = "remotion"

    def __init__(
        self,
        renderer_dir: Path,
        *,
        browser_executable: str | None = None,
        chrome_mode: str = "headless-shell",
        concurrency: int | None = None,
        crf: int = 18,
    ):
        self.renderer_dir = Path(renderer_dir)
        self.browser_executable = browser_executable
        self.chrome_mode = chrome_mode
        self.concurrency = concurrency
        self.crf = crf

    @classmethod
    def from_settings(cls, s: WorkspaceSettings) -> "RemotionRenderer":
        rdir = Path(os.environ.get("FRAMEFORGE_RENDERER_DIR") or REPO_RENDERER_DIR)
        browser = os.environ.get("FRAMEFORGE_BROWSER") or s.browser_executable
        chrome_mode = os.environ.get("FRAMEFORGE_CHROME_MODE") or s.chrome_mode
        return cls(rdir, browser_executable=browser, chrome_mode=chrome_mode, concurrency=s.render_concurrency, crf=s.crf)

    # ---------------------------------------------------------------- checks

    def _node(self) -> str:
        node = shutil.which("node")
        if not node:
            raise FrameForgeError("Node.js not found.", hint="Install Node.js 18+ (Windows: 'winget install OpenJS.NodeJS.LTS').")
        return node

    def _script(self) -> Path:
        script = self.renderer_dir / "scripts" / "render-scenes.mjs"
        if not script.is_file():
            raise FrameForgeError(f"Renderer not found at {self.renderer_dir}.", hint="Set FRAMEFORGE_RENDERER_DIR to the repo's renderer/ folder.")
        if not (self.renderer_dir / "node_modules" / "@remotion" / "renderer").is_dir():
            raise FrameForgeError(
                "Renderer dependencies are not installed.",
                hint=f"Run 'npm ci' in {self.renderer_dir}.",
            )
        if self.browser_executable and not Path(self.browser_executable).is_file():
            raise FrameForgeError(
                f"Browser not found: {self.browser_executable}",
                hint="Fix FRAMEFORGE_BROWSER / browser_executable, or unset it to let Remotion manage Chrome.",
            )
        return script

    def fingerprint(self) -> str:
        files: dict[str, str | None] = {}
        for pattern in _FINGERPRINT_GLOBS:
            for p in sorted(self.renderer_dir.glob(pattern)):
                if p.is_file():
                    files[p.relative_to(self.renderer_dir).as_posix()] = hash_file(p)
        return hash_data(files)

    # ---------------------------------------------------------------- render

    def render(self, request: RenderRequest, on_event=None) -> None:
        if not request.jobs:
            return
        node, script = self._node(), self._script()
        bundles = request.cache_dir / "bundles"
        bundles.mkdir(parents=True, exist_ok=True)
        bundle_dir = bundles / f"{self.fingerprint()[:16]}-{request.assets_key[:12]}"
        job = {
            "bundleDir": str(bundle_dir),
            "publicDir": str(request.public_dir) if request.public_dir else None,
            "browserExecutable": self.browser_executable,
            "chromeMode": self.chrome_mode,
            "concurrency": self.concurrency,
            "crf": self.crf,
            "x264Preset": "veryfast",
            "scale": request.scale,
            "scenes": [{"id": j.scene_id, "output": str(j.output), "props": j.props} for j in request.jobs],
        }
        with tempfile.TemporaryDirectory() as td:
            job_path = Path(td) / "job.json"
            job_path.write_text(json.dumps(job), encoding="utf-8")
            proc = subprocess.Popen(
                [node, str(script), str(job_path)],
                cwd=self.renderer_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if on_event:
                    on_event(event)
            stderr = proc.stderr.read() if proc.stderr else ""
            code = proc.wait()
        if code != 0:
            tail = "\n".join(stderr.strip().splitlines()[-12:])
            raise FrameForgeError(f"Remotion render failed (exit {code}):\n{tail}", hint=_hint_for(stderr))


def _hint_for(stderr: str) -> str:
    s = stderr.lower()
    if "browser" in s or "chrome" in s or "headless" in s:
        return ("Remotion could not start Chrome. Let it download its own (unset FRAMEFORGE_BROWSER), or point "
                "FRAMEFORGE_BROWSER at Chrome and set chrome_mode: chrome-for-testing.")
    if "cannot find module" in s:
        return "Renderer dependencies look incomplete; run 'npm ci' in renderer/."
    return "Check the renderer output above; 'npm run studio' in renderer/ previews scenes interactively."
