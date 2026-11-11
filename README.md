# FrameForge

Local-first pipeline that turns a concept into a narrated MP4, with human
approval gates. A Mostly Human Studio tool. See `PLAN.md` for the roadmap.

**Status: M2.** Projects, approval gates, creative planning and rendering
work: `build` produces a validated, **silent** MP4. Narration and captions
arrive in M3.

## Setup (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

macOS/Linux: same steps, using `python3 -m venv .venv && source .venv/bin/activate`.

### Renderer (needed for `build`)

```powershell
winget install OpenJS.NodeJS.LTS      # Node 18+
winget install Gyan.FFmpeg            # ffmpeg + ffprobe on PATH
cd renderer; npm ci; cd ..
```

On the first render, Remotion downloads its own headless Chrome. To use an
existing Chrome instead, set `FRAMEFORGE_BROWSER` to its path and
`chrome_mode: chrome-for-testing` in `config/settings.yaml`.

Preview templates interactively: `cd renderer; npm run studio`.

Real-render tests are opt-in (slow):
`$env:FRAMEFORGE_TEST_REMOTION=1; pytest -m remotion`.

## Commands

```bash
frameforge create "Explain how an AI agent works" --duration 60 --profile technical-dark
frameforge plan <id> --source examples/llm-api-explainer.md   # offline draft from a doc
frameforge plan <id>                                          # concept only → TODO skeleton
frameforge plan <id> --director external                      # Claude Code writes the files
frameforge validate <id>
frameforge approve <id> --stage creative|final [--note "..."]
frameforge build <id> [--scale 0.5] [--scene s03] [--force]
frameforge status <id> [--json]
frameforge list
frameforge schema brief|storyboard
```

`plan` never overwrites your edits unless you pass `--force`. Even then, it
copies the current files to `history/<timestamp>/` first.

## The three creative files

| File | Holds | Format |
|---|---|---|
| `brief.md` | Why: audience, objective, key message, target length | YAML front matter + notes |
| `script.md` | What is **said** | `# Title`, then `## s01 — Scene title` sections of narration. `<!-- comments -->` are never spoken. |
| `storyboard.json` | What is **shown** | Scenes with `template` + `props`. Run `frameforge schema storyboard` for the schema. |

Script and storyboard are joined by scene id (`s01`, `s02`…), and ids never
change. Narration lives only in the script, so the two files can't disagree.

Templates: `title`, `text-reveal` (≤6 bullets), `architecture-diagram`
(zones marked `internal` or `external`; edges reveal in order), `image`
(file in `assets/`), `morph` (liquid text morph, e.g. product name into
studio wordmark, with an optional tagline).

Design profiles can set `background.style: grid-glow`: a static dot grid,
colour glows and a vignette behind every scene. It's static on purpose, so cuts
are seamless and scenes stay independently cacheable.

Validation blocks approval for: missing or invalid files, scene ids that don't
match, diagram references that don't resolve, asset paths outside `assets/`,
and any leftover `TODO` text. Missing assets and a length more than ±10% off
target are warnings at plan time; missing assets become errors at build.

## Building

`build` renders each scene to its own segment in `scenes/`, then joins them
losslessly into `output/final.mp4`. Every file is checked with ffprobe
(codec, size, fps, frame count, duration).

- **Caching:** each segment is keyed by its scene JSON, the design system,
  timing, size and the renderer code. Rebuilding re-renders only scenes whose
  key changed: edit one scene and one scene renders. Changing the design or
  the renderer code re-renders everything.
- `--scene s03` renders one scene for preview and skips the final video.
- `--scale 0.5` makes quick 960x540 drafts. Draft segments are cached
  separately from full-size ones.
- Until M3, each scene's length is estimated from its narration word count
  (`narration_wpm`, minimum `min_scene_s`).
- `renderer: placeholder` in settings renders colour cards through FFmpeg, with
  no Node or browser. Good for checking timing. The test suite uses it.

## Source documents (offline director)

The stub director turns a Markdown document into a draft. See
`examples/llm-api-explainer.md`:

- optional front matter → brief fields (`audience`, `objective`, `key_message`, `subtitle`, `tone`)
- `# Title` + intro paragraphs → title scene
- each `## Section` → one scene: paragraphs become narration; then a
  ```` ```diagram ```` YAML block → diagram, an `![caption](assets/x.png)` → image,
  bullets → text reveal, and anything else → title card
- a ```` ```scene ```` YAML block (`template:` + `props:`) sets any template
  exactly, e.g. a `morph` outro. `frameforge schema storyboard` lists them all.

`examples/frameforge-promo.md` is FrameForge's own promo video, made with FrameForge.

## With Claude Code

`frameforge plan <id> --director external` writes `DIRECTOR.md` and JSON
schemas into the project. Point Claude Code at that file. It writes the
three files and runs `frameforge validate` until it's clean. **You** run
`approve`.

Projects are created under `./projects/`, or under `$FRAMEFORGE_HOME/projects/` if that variable is set.

### Exit codes
| Code | Meaning |
|---|---|
| 0 | OK |
| 1 | General error (message + hint on stderr) |
| 2 | Project not found |
| 3 | Approval required or stale |
| 4 | Missing artifact |
| 5 | Corrupt or newer-schema `project.json` |
| 6 | Creative files invalid |

## How approvals work

`approve` records the SHA-256 of each gated file. Editing any of them after
approval makes the approval **stale**, and `build` refuses to run until you
approve again. `status` shows exactly which files changed.

- Creative gate: `brief.md`, `script.md`, `storyboard.json`, `design-system.yaml`
- Final gate: `output/final.mp4`, `review/report.json`

## Design profiles

Profiles live in `config/profiles/<name>.yaml` and need a `version`. Each new
project copies its profile into `design-system.yaml` and records the version
in use, so later edits to the shared profile don't change existing projects.

## Costs, secrets, telemetry

FrameForge makes no network calls of its own. Provider keys (from M6) come only
from environment variables.

**Remotion usage events:** Remotion's renderer posts a usage event to
remotion.pro whenever a `licenseKey` is passed, including `"free-license"`.
FrameForge never passes one, so renders send nothing. That also triggers a
"pass licenseKey" warning, which is hidden by `logLevel: "error"`.
`tests/test_renderer_contract.py` fails if a key is ever added. The only
network access is Remotion's one-time Chrome download, when no
`FRAMEFORGE_BROWSER` is set.

## Licensing note

The renderer (M2+) uses Remotion. Its Free License covers individuals and
organizations of up to 3 people, counting collaborators' combined headcount.
At 4+ people, buy a Company License.
