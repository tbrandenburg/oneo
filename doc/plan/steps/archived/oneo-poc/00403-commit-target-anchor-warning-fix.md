> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Commit the target_anchor warning fix (Step 00402) to git

## Why this matters

Step 00402 (fix Neo4j warning for unresolved `LINKS_TO.target_anchor`)
was fully and correctly implemented and independently re-verified during
review:

- `apply_schema()` in `src/oneo/neo4j_store.py` now registers the
  `target_anchor` property key token via
  `CREATE INDEX okf_links_to_target_anchor IF NOT EXISTS FOR
  ()-[r:LINKS_TO]-() ON (r.target_anchor)`.
- `write_links()` now only `SET`s `r.target_anchor` conditionally via a
  `FOREACH (... CASE WHEN row.target_anchor IS NOT NULL ...)` guard.
- `export_graph()` reads the property via `coalesce(r.target_anchor,
  null)`.
- `tests/integration/test_neo4j_store.py::test_anchor_less_link_read_emits_no_driver_warning`
  passes against a live Neo4j instance and confirms no
  "property key does not exist" driver warning is emitted, and that
  `target_anchor` still reads back as `None`.
- Manual re-verification via `oneo reset` + `oneo index ./knowledge
  --no-embeddings` + `Neo4jStore.export_graph()` produced zero warnings.
- The full suite (`pytest tests/unit tests/integration`, 18 integration
  + 71 total) passes.

However, at review time `git status` showed the entire diff
(`src/oneo/neo4j_store.py`, `tests/integration/test_neo4j_store.py`,
and the `AGENTS.md` lessons-learned update) sitting **uncommitted** in
the working tree. This is the same "uncommitted step" pitfall already
recorded in `AGENTS.md` as having recurred three times before (for the
bootstrap step, step 00305, and step 00400) — it is now recurring a
fifth time. An uncommitted step is not durable or reproducible from a
clean checkout: if the working tree were discarded or a fresh clone
were made right now, this fix — including its regression test — would
silently vanish, and the warning would resurface with no record of why
it was ever fixed.

## Actions

1. Run `git status` and `git diff --stat` to confirm the exact set of
   files changed by Step 00402 (expected: `src/oneo/neo4j_store.py`,
   `tests/integration/test_neo4j_store.py`, `AGENTS.md`).
2. Stage and commit exactly those files with a concise commit message
   describing the fix (e.g. "Fix Neo4j target_anchor property-key
   warning for anchor-less LINKS_TO edges").
3. Do not bundle unrelated untracked files (e.g. step-file moves under
   `doc/plan/steps/`) into this commit unless they are also verified to
   belong to this same change; handle plan-file bookkeeping separately
   per the normal step-closing process.
4. After committing, re-run `git status` and confirm the working tree
   is clean with respect to the Step 00402 changes.
5. Re-run `pytest tests/unit tests/integration` once more against the
   committed state to confirm nothing was lost in the commit (e.g. a
   forgotten `git add`).
