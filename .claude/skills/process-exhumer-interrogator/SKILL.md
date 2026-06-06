---
name: process-exhumer-interrogator
description: >
  Stage 1 of the process-exhumer pipeline. Turns a vague task or goal into a
  single, clean **root contract** (behavior + resolvable inputs/outputs) through
  multi-turn dialog with a human. Use when starting a process-exhumer run, or
  whenever you need to sharpen a fuzzy task into a checkable contract before
  decomposition. Produces a structured artifact that decomposition consumes
  without re-asking the user.
---

# Process-Exhumer · Interrogator (Stage 1)

The first stage of the process-exhumer pipeline. Its only job is to produce the
**root contract** — a declaration of *what the task is* — sharp enough that the
decomposition stage can proceed without coming back to the user.

This stage is **single-context, human-in-the-loop dialog**. It must not be run
in a subagent: it is a conversation. (Downstream stages may use subagents; this
one cannot.)

## What this stage does — and does not — do

- **Does:** clarify intent into a checkable `behavior`, and resolve `inputs` /
  `outputs` as far as is meaningful at the root.
- **Does NOT:** decompose. It never asks "what are the steps/parts." That is the
  next stage's job. This stage treats the task as one unit and asks only "what
  *is* this unit?"

Keeping that boundary clean is what makes the contract liftable and the pipeline
portable. If you find yourself enumerating sub-tasks, you have left this stage.

## How to run it

1. Take the user's task description (however vague) as input.
2. Follow the model-agnostic stage prompt in [`prompt.md`](prompt.md): interrogate
   until the stop criterion is met, applying the out-of-domain gate.
3. Present the draft root contract, invite correction, and finalize on user
   confirmation.
4. Emit the final root contract as a fenced ` ```json ` block exactly matching the
   Output schema in `prompt.md`. That block is the handoff to decomposition.

`prompt.md` is the real artifact — self-contained and model-agnostic, so it can be
lifted and run against another model or a future MCP tool. This `SKILL.md` is only
the Claude-Code harness around it.
