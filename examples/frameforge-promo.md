---
subtitle: Write it down. Get a video. Stay in charge.
audience: Developers, educators and small studios who explain technical ideas on video
objective: Show what FrameForge does and why its approval-first, local-first design matters
key_message: FrameForge turns a Markdown doc into a finished video, and nothing renders until you approve it.
duration_s: 56
tone: confident, dry, a little playful
---

# FrameForge

You already wrote the explanation. FrameForge turns it into the video.

## From doc to video

Write a Markdown document. FrameForge drafts the brief, the script, and a storyboard. You review, you approve, it builds.

- Write a Markdown doc
- Review the brief, script and storyboard
- Approve it
- Build the video

## How it flows

Your doc goes in. FrameForge drafts the plan, hands it back for review, and only renders once you say yes.

```diagram
zones:
  - { id: write, label: "You write", kind: internal }
  - { id: draft, label: "It drafts", kind: external }
  - { id: decide, label: "You decide", kind: internal }
  - { id: build, label: "It builds", kind: external }
nodes:
  - { id: doc, label: "Your doc", zone: write }
  - { id: plan, label: "Plan", zone: draft }
  - { id: ok, label: "Approve", zone: decide }
  - { id: render, label: "Render", zone: build }
  - { id: mp4, label: "MP4", zone: build }
edges:
  - { from: doc, to: plan, label: "source", style: request }
  - { from: plan, to: ok, label: "review", style: request }
  - { from: ok, to: render, label: "yes", style: request }
  - { from: render, to: mp4, label: "join", style: stream }
```

## You stay in charge

Generation is never approval. Edit a file after approving, and the approval resets. Placeholder text can't be approved at all.

- Nothing renders until you approve
- Edit after approving? Approval resets
- Placeholders can't be approved

## Change one scene, rebuild one scene

Every scene is cached by its content. Change one, and only that one renders again. Same input, same frames.

- Every scene cached by content
- Untouched scenes are reused
- Same input, same frames

## Local-first

It runs on your machine and sends nothing home. Claude Code can direct the creative work. It just can't approve it.

- Runs on your machine
- No telemetry by default
- Claude Code directs; you approve

## This video was a Markdown file

That's the pitch. This entire video started life as a Markdown file.

```scene
template: title
props:
  heading: This video was a Markdown file.
  subheading: Every scene, every diagram, every word.
```

## Made by

FrameForge. Made by Mostly Human Studio, for people who would rather write than edit.

```scene
template: morph
props:
  from: FrameForge
  to: Mostly Human Studio
  tagline: Makers of FrameForge
```
