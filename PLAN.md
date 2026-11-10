# FrameForge — Implementation Plan

Companion to `FrameForge_MVP_Spec.md` (v0.1). This plan covers the decisions,
risks and milestones from spec §14 step 2. Implement it in order: each
milestone ships with its tests and leaves a working CLI behind it.

## 1. Decisions (settled)

| Decision | Choice | Why |
|---|---|---|
| Owner / use | Mostly Human Studio; output is shared publicly | Sets the license and quality bar |
| Renderer | Remotion + FFmpeg, behind a `Renderer` interface | Free License covers individuals and orgs up to 3 people. **Collaborations count combined headcount**: 4+ people total means a Company License. Re-check if the team grows. |
| Default TTS | Kokoro (Apache-2.0), local CPU | No per-character cost, good quality. Piper is the GPL fallback, not bundled. |
| Platform | Windows-native first; Linux CI | Matches the working stack. Use `pathlib` everywhere and never shell out with string-joined paths. |
| Director | Claude Code writes stage files; CLI validates. Optional API adapter later. | No API spend by default. Deterministic stages don't depend on Claude Code (spec §5). |
| Python | 3.11+, Typer CLI, Pydantic v2 models, PyYAML | |
| Image generation | Deferred | The demo is diagrams. MVP ships a `local` asset provider only. |

## 2. Core design

### 2.1 `storyboard.json` is the contract
Every stage downstream of Creative reads the storyboard. A scene has a stable
`id` (never renumbered), a `template`, `narration` text, template `props`, and
optional `assets`. Templates live in the Remotion project and are selected
by name.

### 2.2 Approvals are bound to content hashes
`approve --stage creative` records the SHA-256 of `brief.md`, `script.md`,
`storyboard.json` and the project's `design-system.yaml`. An approval is
valid only while those hashes still match. Editing an approved file voids the
approval automatically, so "never treat generation as approval" is enforced
by code. `approve --stage final` binds to the output MP4 and the review report.

### 2.3 Per-scene dependency chain and segment cache
```
script/narration text ─► narration WAV ─► scene duration ─┐
design profile ───────────────────────────────────────────┼─► scene segment MP4 ─► final MP4
scene props + assets ─────────────────────────────────────┘        (concat + mux + captions)
```
- Each node's key is the hash of its inputs. Matching key → skip.
- Each scene renders to `scenes/<scene-id>.<hash>.mp4`, and the final video is an FFmpeg concat.
- **Constraint:** no cross-scene transitions. Each scene owns its in and out
  transitions so segments concatenate cleanly.
- Profile change → re-render segments, keep audio. One scene's narration
  change → that scene's audio, segment and the final video only.

### 2.4 Duration
Narration length drives scene length (audio + configurable padding).
`--duration` is a target. The validator warns outside ±10% and never
time-stretches audio.

### 2.5 Determinism
"Deterministic" means: same input hashes → the render is skipped, and a forced
re-render produces identical frames. MP4 bytes are not compared (container
metadata varies by machine). Tests hash sampled frames extracted by FFmpeg.

### 2.6 Design profiles
Shared profiles live in `config/profiles/<name>.yaml` and carry a `version`.
`create` copies the profile into the project as `design-system.yaml` and records
the name, version and hash in `project.json`. Later profile edits don't
silently change existing projects.

### 2.7 State
`projects/<id>/project.json`, written atomically (temp file + `os.replace`).
It holds the settings, the profile snapshot, per-stage status and hashes,
approvals with their bound hashes, and per-scene cache keys. Everything can be
resumed from this file and the files on disk.

## 3. Milestones

| # | Increment | Acceptance tests proven |
|---|---|---|
| **M0** | Package skeleton, Typer CLI, `project.json` state, hashing, `create` / `status` / `list` / `approve` primitives | AT6 (resume), approval hash-binding |
| M1 | Pydantic schemas for brief/script/storyboard; stub director (Markdown → scenes, offline); `plan`; `build` blocked without valid creative approval | AT1, AT2 |
| M2 | Remotion project: `title`, `text-reveal`, `architecture-diagram` templates; silent single-scene render from props; ffprobe validator | First MP4 |
| M3 | `VoiceProvider` interface: `fixture` (supplied WAVs) + `kokoro`; scene durations from audio; captions (SRT + burned-in via Remotion); mux | AT3 |
| M4 | Segment cache + concat; `revise --scene <id> --file <patch.json>` (offline) and `--instruction` (director) | AT5 |
| M5 | `review`: validation report (streams, codecs, dimensions, duration, missing assets) + static HTML page with video and per-scene thumbnails; final gate | AT4 |
| M6 | Optional Anthropic API director adapter; cost ledger; spend cap; secrets from env only; error redaction; telemetry audit of all deps | AT7, AT8 |
| M7 | Demo: 60 s "How an AI application communicates with an LLM API" | Definition of done |

**M2 is the riskiest step** (Remotion props, fonts, Windows paths). Get a
three-scene silent render working before touching audio.

### Demo storyboard sketch (M7)
1. Hook: "What actually happens when your app calls an LLM?"
2. The boundary: your app + backend (one color zone) vs. the external model API (another)
3. Building the request: system prompt, messages, parameters, API key held server-side
4. Over the wire: HTTPS request to the provider; auth, rate limits
5. The response: tokens stream back, the backend parses and the app renders
6. Recap: what your code owns and what the provider owns

## 4. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Kokoro on Windows needs extra native deps | Spike in M3 before building on it. `fixture` provider keeps the pipeline testable regardless. |
| Remotion headless Chrome download / fonts on Windows | Pin the Remotion version; bundle fonts in `renderer/public/fonts`; document first-run setup. |
| Caption timing drift | M3: sentence chunks timed proportionally within each scene. Word-level timing is a later upgrade. |
| Telemetry in dependencies | M6 audit: npm/pip deps, Remotion CLI, Chrome flags. AT8 covers anything sent off the machine. |
| Scope creep in the director | The director is the least important part. Most of the definition of done is state and invalidation. |
| License drift | If a collaborator joins and the combined headcount reaches 4+, buy a Remotion Company License or swap the renderer. |

## 5. Repository layout (as built)

```text
frameforge/
├── PLAN.md
├── README.md
├── pyproject.toml
├── config/
│   ├── settings.yaml
│   └── profiles/technical-dark.yaml
├── src/frameforge/
│   ├── cli.py          # Typer entry point
│   ├── state.py        # project.json model, atomic IO, approvals
│   ├── hashing.py      # file/dict hashing
│   ├── paths.py        # workspace + project path resolution
│   ├── profiles.py     # design profile loading + snapshot
│   ├── errors.py       # user-facing errors with recovery hints
│   └── pipeline/       # stage modules (M1+)
├── renderer/           # Remotion project (M2+)
├── templates/
├── projects/           # gitignored
└── tests/
```
(The spec's top-level `pipeline/` becomes `src/frameforge/pipeline/` so it
installs as a package.)
