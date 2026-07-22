> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Remove Stray Tooling Files Committed with the Bootstrap

## Why this matters

Review of the bootstrap commit (`6b5bde0`, created by step
00101-commit-bootstrap-project-to-git) found two top-level files that are
not part of the Oneo project as described by the plan and are not
referenced by any step's actions:

1. `oneo-implementation-plan.md` — a byte-for-byte duplicate of
   `doc/plan/plan.md` (`diff doc/plan/plan.md oneo-implementation-plan.md`
   produces no output). Having the same 2170-line plan committed twice at
   two different paths is pure clutter: it can silently drift out of sync
   with the canonical `doc/plan/plan.md` and confuse anyone trying to find
   "the" plan document.
2. `factory_v2.sh` — a 616-line agent-orchestration script (`factory.sh`
   equivalent) that drives the plan-splitting/implement/review/demo
   lifecycle for the *meta* process of building Oneo. It is operator
   tooling for running this very factory workflow, not part of the Oneo
   proof of concept described in `doc/plan/plan.md`, and it was never
   named as a deliverable of any step (00100 through 01000).

Neither file is excluded by `.gitignore`, and both were swept into the
bootstrap commit alongside the real project files
(`pyproject.toml`, `uv.lock`, `src/`, `tests/`, etc.). This pollutes the
"clean, modern uv-managed Python project" the plan calls for and makes it
harder for a future contributor to tell which files are part of the
shipped proof of concept versus internal tooling used to build it.

## Actions

1. Confirm `oneo-implementation-plan.md` remains an exact duplicate of
   `doc/plan/plan.md` (re-run `diff` before removing) and, if so, delete
   `oneo-implementation-plan.md` from the repository, keeping
   `doc/plan/plan.md` as the single canonical plan document.
2. Relocate `factory_v2.sh` out of the project root — either into a
   dedicated `tools/` or `.factory/` directory that is clearly separated
   from the shipped Oneo package, or remove it from version control
   entirely if it is only ever run from outside the repo. If kept, add a
   short comment/README note clarifying it is orchestration tooling for
   building this repository, not part of the Oneo CLI/package.
3. Re-run `git status` and `uv run pytest -q` after the change to confirm
   the working tree is clean and no test or packaging step depended on
   either file's prior location.
4. Commit the cleanup with a message that references this gap-fill step.
