> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Commit the Neo4j projection implementation to git

## Why this matters

Step 00400 ("Implement the Neo4j Projection") was fully and correctly
implemented and tested (53 unit tests + 17 integration tests pass, and
the full `oneo reset` / `oneo index ./knowledge --no-embeddings` /
`oneo verify` end-to-end validation passes against a live Neo4j
instance), but the work was **never committed**. `git status` at
review time showed all of the step's files as modified/untracked in
the working tree, still sitting on top of commit `b85492e` (Step
00304).

This is the same uncommitted-step pitfall already documented in
AGENTS.md for steps 00101 and 00304 (and now recurring a fourth/fifth
time). An uncommitted step is not durable or reproducible from a clean
checkout, even though the working tree is correct. Per AGENTS.md:
"Treat 'run `git status` and commit' as a mandatory last action item
on every implementation step."

## Actions

1. Run `git status` and `git diff` to review every change belonging to
   Step 00400: `src/oneo/cli.py`, `src/oneo/models.py`,
   `src/oneo/neo4j_store.py`, `src/oneo/pipeline.py`,
   `src/oneo/validation.py`, and the corresponding test files under
   `tests/unit/` and `tests/integration/`.
2. Stage exactly those files (do not include unrelated in-flight work).
3. Commit with a message referencing Step 4 / Step 00400, following the
   existing commit message style (e.g. `git log --oneline` history).
4. Verify with `git status` that the working tree is clean with respect
   to these files after the commit.
5. Do not move or edit the immutable step file
   `doc/plan/steps/in-review/00400-implement-the-neo4j-projection.md`;
   only the step's own commit is missing, not its record.
