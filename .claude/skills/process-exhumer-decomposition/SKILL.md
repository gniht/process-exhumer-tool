---
name: process-exhumer-decomposition
description: >
  Stage 2 of the process-exhumer pipeline. Recursively decomposes a root
  contract (from the interrogator) into a tree of contract-bound nodes — each
  internal node carrying an assembly pattern, deterministic glue, and named
  child contracts — until every leaf is declared ready to codify. Use after
  the interrogator emits a root contract, or on any contract that needs
  decomposing. Produces the node tree that codification consumes.
---

# Process-Exhumer · Decomposition (Stage 2)

The load-bearing stage. It consumes a **contract** and answers the recursion's
two questions — *what am I made of?* (child contracts) and *how do you build
me?* (assembly pattern + glue) — repeatedly, until every path ends in a leaf.

The stage prompt in [`prompt.md`](prompt.md) is **flat**: one contract in, one
decision out, no tree context. The recursion lives *here*, in the harness, as
a plain worklist loop. This mirrors the long-term architecture (stateless
stage-tools; the tree-walk is an orchestration concern) and keeps the prompt
liftable.

## What this stage does — and does not — do

- **Does:** turn one root contract into a full tree of nodes; decide
  codify-vs-decompose at every node; resolve child I/O to what the wiring
  needs.
- **Does NOT:** write leaf implementations (codification's job), check
  contracts against code (verification's job), or predict which leaves will
  need AI (discovered during codification, recorded in the node's `result`).

## How to run it

1. **Input:** a root contract — the interrogator's final ```json block from
   this conversation, a pasted contract, or a file. Optionally a target
   language for glue (default: python).
2. **Initialize** the tree with a root node `{ "id": "n1", "contract": ... }`
   and a worklist containing it. Ids are opaque (`n1`, `n2`, ... in creation
   order) — never positional paths.
3. **Loop — while the worklist is non-empty:** take a node, apply `prompt.md`
   to its contract *alone* (plus the language). Do not pass tree context,
   siblings, or conversation history — flatness is the portability
   discipline, not an inconvenience.
   - `decision: "codify"` → store the resolved contract on the node; it is a
     leaf. Done with this node.
   - `decision: "decompose"` → store the resolved contract,
     `assembly_pattern`, and `glue` on the node; for each child
     `{name, contract}`, create a node with a fresh id, attach it under the
     parent with its local `name` (the name is the edge label — parent-scoped
     wiring, not part of the node), and add it to the worklist.
   - `decision: "reject"` → **stop and surface it.** A rejected child means
     its parent's decomposition mis-specified it: show the user the reason
     and re-run the parent node. If the root itself is rejected, send the
     user back to the interrogator. Do not silently retry the child.
4. **Guards:** if depth exceeds 5 or the tree exceeds 25 nodes, pause, show
   the tree shape, and check with the user before continuing.
5. **Emit** the finished tree as a single fenced ```json block — the handoff
   to codification:

   ```json
   {
     "id": "n1",
     "contract": { "...": "..." },
     "assembly_pattern": "...",
     "glue": "...",
     "children": [
       { "name": "stage_one", "id": "n2", "contract": { "...": "..." } }
     ]
   }
   ```

   A node with `assembly_pattern`/`glue`/`children` is internal; a node
   without them is a leaf awaiting codification. For long runs, also write
   the tree to a file if the user wants one.

## Subagents (later)

Each prompt application is flat — contract in, decision out — so it is a
natural subagent call. Per the spec, default to single-context while the
prompt is young; pull subagents in to validate contract discipline once it
stabilizes.

`prompt.md` is the real artifact — self-contained and model-agnostic, so it
can be lifted and run against another model or a future MCP tool. This
`SKILL.md` is only the Claude-Code harness (and v1 orchestrator) around it.
