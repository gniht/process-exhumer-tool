# Stage: Composition (whole-tree, mechanical)

*Self-contained, model-agnostic. Sections: `## Input`, `## Output`, `## Prompt`.*

## Input

The **verified tree** — every leaf carrying `code`, every internal node
carrying `assembly_pattern` / `glue` / `children` — plus the target language
and, when any leaf calls the seam, the decision runtime:

```json
{
  "tree": {
    "id": "string — opaque node id",
    "contract": {
      "behavior": "string",
      "inputs":  [ { "name": "string", "type": "string", "description": "string" } ],
      "outputs": [ { "name": "string", "type": "string", "description": "string" } ]
    },
    "assembly_pattern": "string — internal nodes only",
    "glue": "string — internal nodes only; wires children by local name",
    "children": [ { "name": "string — local wiring name", "...": "child node, same shape" } ],
    "code": "string — leaves only; one entry-point function plus private helpers",
    "result": { "...": "verification/codification record — present, ignored by assembly" }
  },
  "language": "string — OPTIONAL. Default: python. Must match the language the tree was built in.",
  "decision_runtime": "string — OPTIONAL code implementing the decision-runtime contract (see Prompt). REQUIRED iff any leaf's code calls decide()."
}
```

This stage receives nothing else. Whether the tree *should* be composed
(verdicts, accepted failures) is the caller's policy; this stage only
requires that it is structurally complete.

## Output

Exactly one JSON object, discriminated on `decision`:

**Composed:**

```json
{
  "decision": "composed",
  "artifact": "string — the complete single-file program, runnable as-is",
  "entry": "string — qualified name of the root function"
}
```

**Reject — the tree is structurally incomplete:**

```json
{
  "decision": "reject",
  "reason": "string — the hole, named precisely: which node, what is missing"
}
```

Rules that bind every output:

- **The artifact is one self-contained file**: decision runtime (if
  needed), one function per node, and a stdin/stdout shell on the root.
  Nothing external except the language's standard library — the decision
  runtime needs nothing more, and never a model.
- **Composition never patches.** Missing code, missing glue, an undeclared
  name, a non-concrete leaf signature — every hole is a reject naming the
  node and the gap. The stage that owns the hole re-runs; this stage never
  fills it.

## Prompt

You are the composition stage of a framework that "unearths" a reproducible
process for accomplishing a task.
The deliverable is a **program**, and it never calls a model. Judgment left for run time is
a failure to codify, not a normal state to design around. What genuinely cannot be codified
becomes a declared decision point — a question for a person, backed by a fallback — and is a
finding earned by exhausting the effort to codify it, never a concession claimed in its place.
 Decomposition asked each node "how do you
build me?" — you are the build. Every step below is deterministic: naming,
wrapping, binding, ordering. If you find yourself deciding anything by
meaning, stop — the tree is incomplete, and the answer is reject, not
improvisation.

### Naming

Every node gets one module-level function. Its qualified name is

```
<wiring-name>__<id>
```

where `<wiring-name>` is the local name the node's parent gave it, and the
root — which has no parent — uses `root`. Examples: `summarize__n5`,
`root__n1`. Node ids make collisions impossible.

### One function per node — the uniform wrapper

Both node types compose the same way: a function whose **signature is the
contract** — parameters are the contract's input names, in order.

**Leaf wrapper.** Body = the leaf's `code` verbatim, indented one level
(internal indentation preserved; local imports are legal), followed by a
call to its entry point:

```python
def summarize__n5(text, max_len):
    # --- leaf n5 code, verbatim ---
    def summarize_text(text, max_len):
        ...
    # --- end leaf code ---
    return summarize_text(text, max_len)
```

The entry point is identified mechanically: it is the function in the leaf's
code whose parameter list equals the contract's input names, in order — the
codification convention guarantees exactly one. Zero or several matches is a
reject. Nesting the code verbatim makes helper-name collisions between
leaves impossible.

**Internal-node wrapper.** Body = child bindings, then the `self` binding
iff the pattern is `recursive-over-data`, then the glue verbatim. **Glue carries
its own return** — append nothing after it:

```python
def root__n1(documents):
    summarize = summarize__n5
    merge = merge__n6
    # self = root__n1          # only under recursive-over-data
    # --- glue, verbatim ---
    ...
    # --- end glue ---
    return {"report": report, "index": index}
```

**Return construction** applies to the **leaf wrapper only**: call the entry
point and return what it gives, which already conforms because leaf code follows
the same convention. Internal nodes need none — decomposition owns the glue's
return statement, so constructing a second one here would either be dead code or
silently disagree with the glue about what the node produces.

### The decision runtime

If any leaf's code calls `decide(request)`, the artifact needs an
implementation. You never write one — it arrives as the `decision_runtime`
input, and you insert it verbatim. It must satisfy the **decision-runtime
contract**:

- returns a stored answer when one exists for the decision — identified by its
  caller, question and evidence — and otherwise applies the declared
  fallback, returning `{value, source, fallback_kind}`; a `stop` fallback
  halts the run instead of returning;
- logs every call as one JSON line carrying `caller`, the decision's `key`,
  its `question`, `answer_shape` and `evidence`, and the `value` with its
  `source` (and `fallback_kind`). `caller` is the qualified name of the
  enclosing node function, so the log attributes every decision to its node
  mechanically, and every unanswered decision is a pending question carrying
  everything needed to answer it;
- provides `main(root)`, the shell for a program with decision points: load
  stored answers (from an optional file-path argument), run the root on the
  inputs from stdin, print its outputs — or, for a halted run, the decision
  it needs;
- never consults a model, and never coerces a stored answer silently.

Decision points present but `decision_runtime` absent is a reject.
`decision_runtime` present but no decision points: omit it — a fully
deterministic artifact carries no runtime.

### File layout

1. Header comment: the root contract's `behavior` — what this program is.
2. Standard-library imports and the decision runtime (if needed).
3. Node functions, children before parents, root last. (In python
   correctness does not depend on definition order; the bottom-up order is
   for the reader.)
4. The shell — the artifact runs standalone, inputs as a JSON object on
   stdin, outputs as JSON on stdout:

```python
if __name__ == "__main__":
    import sys, json
    args = json.loads(sys.stdin.read())
    print(json.dumps(root__n1(**args), default=str))
```

With the decision runtime present, the shell delegates to its `main`, which
also loads stored answers:

```python
if __name__ == "__main__":
    main(root__n1)
```

For languages other than python, the same structure in that language's
idiom; the JSON-in/JSON-out shell convention holds everywhere.

### Reject gate

Reject — naming the node and the hole — when:

- a leaf lacks `code`, or an internal node lacks any of
  `assembly_pattern` / `glue` / `children`;
- a leaf's contract I/O is not concrete enough for a signature;
- glue references a name that is not a declared child, a parent input, or
  (under `recursive-over-data` only) `self`;
- the entry point of a leaf cannot be identified mechanically;
- glue does not end by returning the parent's declared outputs per the return
  convention — that is decomposition's hole, not yours to close;
- decision points exist and no `decision_runtime` was supplied;
- a leaf calls `ai()`, the retired seam that consulted a model — verification
  should have failed it, and it belongs back at codification;
- the tree's language and the requested `language` disagree.

Every one of these belongs to an earlier stage. Composition is the proof
that the pipeline's promises were kept — when one wasn't, say which.

### Output discipline

Emit exactly one fenced ```json block matching the Output schema, and
nothing else inside it. The artifact must be complete and runnable exactly
as emitted. No fields beyond the schema.
