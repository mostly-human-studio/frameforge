# FrameForge

Local-first pipeline that turns a concept into a narrated MP4, with human
approval gates. A Mostly Human Studio tool. See `PLAN.md` for the roadmap.

**Status: M0.** Project state, design-profile snapshots and approval gates
work. Planning, rendering and narration arrive in M1–M3.

## Setup (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

macOS/Linux: same steps, using `python3 -m venv .venv && source .venv/bin/activate`.

## Commands (M0)

```bash
frameforge create "Explain how an AI agent works" --duration 60 --profile technical-dark
frameforge list
frameforge status <project-id> [--json]
frameforge approve <project-id> --stage creative|final [--note "..."]
frameforge build <project-id>        # enforces the creative gate; renderer lands in M2
```

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

M0 makes no network calls. Provider keys (from M6) come only from environment
variables. Telemetry is off and there is nothing to send.

## Licensing note

The renderer (M2+) uses Remotion. Its Free License covers individuals and
organizations of up to 3 people, counting collaborators' combined headcount.
At 4+ people, buy a Company License.
