> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Commit the Bootstrapped Project to Git

## Why this matters

Step 1 (00100-bootstrap-the-project) explicitly required "a clean, modern
`uv`-managed Python project with a committed lockfile and reproducible
commands." Review of the working tree found that the `main` branch has
**zero commits** — `git log` reports "your current branch 'main' does not
have any commits yet" and `git status` lists every project file
(`pyproject.toml`, `uv.lock`, `src/`, `tests/`, `docker-compose.yml`,
`.gitignore`, `.env.example`, `README.md`, `AGENTS.md`, `doc/`, etc.) as
untracked.

An uncommitted lockfile is not a "committed lockfile," and reproducible
commands cannot be verified from a clean checkout if the checkout itself
does not exist in version control. Every subsequent step in this plan
depends on being able to check out and build on top of the bootstrap
step's work; without a commit there is no stable base to branch from,
diff against, or roll back to. This must be fixed before any later step
proceeds.

## Actions

1. Review `.gitignore` to confirm it correctly excludes `.venv/`,
   `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.coverage`, and `.env`
   (already present) and does not accidentally exclude anything that
   should be tracked (e.g. `uv.lock`, `knowledge/`, `tests/fixtures/`).
2. Stage and commit the full bootstrap project state: `pyproject.toml`,
   `uv.lock`, `src/`, `tests/`, `docker-compose.yml`, `.env.example`,
   `.python-version`, `README.md`, `.gitignore`, and the `doc/plan/`
   contents.
3. Do not commit `.env` (already gitignored) or any local virtual
   environment / cache directories.
4. Verify with `git log --oneline` that the commit exists and with
   `git status` that the working tree is clean (no untracked files that
   should be tracked).
5. Confirm a fresh `git clone` (or `git worktree add`) of the resulting
   commit can run `uv sync && uv run pytest -q` successfully, proving the
   commit is self-contained and reproducible.
