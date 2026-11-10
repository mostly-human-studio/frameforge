# Working on FrameForge

- Read `PLAN.md` first. Work one milestone at a time and land its tests with it.
- `storyboard.json` is the contract between stages. Scene ids are stable; never renumber them.
- Never write approvals on anyone's behalf. Don't call `Workspace.approve` or `frameforge approve` outside tests.
- All state writes go through `Workspace.save` (atomic). Don't hand-edit `project.json` from code.
- Use `pathlib` for every path; Windows is the primary platform.
- Errors raised to users are `FrameForgeError` subclasses with a `hint`.
- No paid API calls, publishing, deploys or destructive changes without explicit approval from Michelle.
- Tests must run offline: use the `fixture` voice provider and the stub director.
