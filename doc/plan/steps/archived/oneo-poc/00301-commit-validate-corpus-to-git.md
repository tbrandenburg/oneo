> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-Fill Step 00301 — Commit the Validation/Loader Work to Git

## Why this matters

Review of step 00300 (validate-and-resolve-the-okf-corpus) found that
`git status` reports the entire implementation — `src/oneo/validation.py`,
`src/oneo/okf_loader.py`, `tests/unit/test_validation.py`,
`tests/unit/test_okf_loader.py`, `tests/unit/test_cli.py`, the `parse`
and `validate` CLI commands in `src/oneo/cli.py`, the new domain models in
`src/oneo/models.py`, the `Oneo.validate`/`Oneo.parse` coordinator methods
in `src/oneo/pipeline.py`, the updated `knowledge/` fixtures (now
including a `type` frontmatter field per OKF spec §9), the new
`markdown-it-py`/`python-frontmatter` dependencies in `pyproject.toml`,
and the `.gitignore`/`AGENTS.md` updates as **untracked or modified,
uncommitted** working-tree changes. `git log --oneline` only shows the
original bootstrap commit plus gap-fill commits for stray tooling files —
none of it includes Steps 2 or 3's actual code.

This repeats the exact failure mode already documented and fixed once in
gap-fill step 00101 ("Commit the Bootstrapped Project to Git"): an
uncommitted implementation is not a durable, reproducible artifact. Any
subsequent step (00400 Neo4j projection, or a fresh clone/checkout) would
start from a tree that is missing the OKF loader and validator entirely,
silently reintroducing work or diverging from what was actually reviewed
and approved in step 00300.

## Actions

1. Review `git status` and confirm exactly which files are the intended
   output of steps 00200/00300 (loader, validation, models, CLI, pipeline,
   tests, `knowledge/` fixture updates, dependency additions,
   `.gitignore`/`AGENTS.md` lesson updates) versus anything that should
   remain untracked (`.venv/`, `__pycache__/`, `build/`, `.env`).
2. Stage and commit all of the above in one or more logically-scoped
   commits (e.g. "Implement OKF-aware loader (Step 2)" and "Implement OKF
   corpus validation and resolution (Step 3)").
3. Move the corresponding closed/in-review plan step files
   (`doc/plan/steps/closed/00200-implement-the-okf-aware-loader.md`,
   `doc/plan/steps/closed/00201-gitignore-the-build-output-directory.md`,
   `doc/plan/steps/in-review/00300-validate-and-resolve-the-okf-corpus.md`)
   into version control as part of the same commit(s) that land the code
   they describe, preserving the existing directory-based step lifecycle.
4. Verify with `git log --oneline` that the commits exist and with
   `git status` that the working tree is clean (no untracked or modified
   files remain that should be tracked).
5. Confirm a fresh `git clone` (or `git worktree add`) of the resulting
   commit can run `uv sync && uv run pytest -q` and
   `uv run oneo validate ./knowledge --strict` successfully, proving the
   commit is self-contained and reproducible.
