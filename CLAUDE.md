# process-exhumer-tool

Project instructions for Claude Code. They live in the repo so they reach every machine; Claude's own memory stays on the machine that wrote it.

## Where things are

- `spec.md` — the architectural spec: goals, the data model, the decision seam, open questions.
- `design-journal.md` — the dated build record. Its **Next** section says where things stand and what is queued; read it before picking up work.
- `.claude/skills/` — the five pipeline stages, each a `prompt.md` wrapped by a thin `SKILL.md`.
- `runs/` — one directory per run: a write-up per stage, every stage's artifact, and the composed program.

## A produced program never calls a model

No exceptions inside generated code, and full codification is always the goal, never "as few model calls as practical". The spec encodes this as the decision seam (`spec.md`, *The decision seam*): irreducible judgment becomes a `decide(request)` decision point, answered from the user's stored answers, with a declared fallback and every fallback value marked. Wiring a model in is the user's deliberate act, outside the program; the framework ships no answerer.

- When a judgment resists codification, offer the nearest codifiable alternative first (often a narrower contract), then a decision point. Never a model call.
- Never describe model calls as a normal part of a generated program, in design talk or in code.
- "The budget for reasoning is almost entirely up-front" means *while the program is being built*, not once per input at run time. Run 2's records misread it that way.

## Two machines

The author works on this repo from two machines, and a session's starting git status is local only: it never shows commits the other machine pushed.

- **At the start of a session,** run `git fetch origin`, fast-forward `main`, and summarize any incoming commits before other work. The fetch may raise the SSH passphrase dialog; that's expected.
- **Before leaving a machine,** commit everything and get it pushed.
- **Rules that should reach both machines go in this file,** not in Claude's memory, which doesn't sync.

## Pushing

The SSH key is passphrase-protected and prompts through a desktop dialog. A `git push` run by Claude can block on that dialog and then fail with "Please make sure you have the correct access rights", which looks like an auth error but isn't. Commit, then ask the author to run `! git push origin main`.
