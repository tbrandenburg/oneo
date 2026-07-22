> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-Fill Step 00303 — Commit the Diagnostic Line-Number Work to Git

## Why this matters

Review of step 00302 (populate-diagnostic-source-line-numbers) found that
`git status` reports `src/oneo/cli.py`, `src/oneo/models.py`,
`src/oneo/okf_loader.py`, `src/oneo/validation.py`, and
`tests/unit/test_validation.py` as modified, uncommitted working-tree
changes, and the `doc/plan/steps/in-review/` directory itself as
untracked. `git log --oneline` shows no commit for step 00302's work at
all — the most recent commit is step 00300/00301's validation work.

This is the exact same recurring failure mode already documented and
fixed twice before (gap-fill steps 00101 and 00301): "implementing a
step's code without committing it recurs across steps." An uncommitted
step is not durable or reproducible from a clean checkout even if the
working tree looks correct. Any subsequent step (00400 Neo4j projection)
would start from a tree silently missing the `line` field plumbing
entirely.

## Actions

1. Review `git status` and confirm exactly which files are step 00302's
   intended output (the `line`-field additions to `models.py`,
   `okf_loader.py`, `validation.py`, `cli.py`, and the corresponding test
   updates) versus anything that should remain untracked.
2. Stage and commit all of the above in a single, logically-scoped commit
   (e.g. "Populate diagnostic source line numbers (Step 00302)").
3. Move `doc/plan/steps/in-review/00302-populate-diagnostic-source-line-numbers.md`
   into `doc/plan/steps/closed/` as part of the same commit, preserving
   the existing directory-based step lifecycle.
4. Verify with `git log --oneline` that the commit exists and with
   `git status` that the working tree is clean.
5. Confirm a fresh `git clone` (or `git worktree add`) of the resulting
   commit can run `uv sync && uv run pytest -q` and
   `uv run oneo validate ./knowledge --strict` successfully.
