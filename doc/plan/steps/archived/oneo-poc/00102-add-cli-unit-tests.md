> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Add Unit Tests for the CLI Layer

## Why this matters

Step 1 (00100-bootstrap-the-project) requires "Unit tests" for its
deliverables and states that CLI command handlers must be thin, parse
input, invoke the `Oneo` coordinator, render results, and map failures to
exit codes. Coverage measurement (`uv run pytest --cov=oneo
--cov-report=term-missing`) shows `src/oneo/cli.py` is only 42% covered,
with the `health` and `files` command bodies (lines 28-38, 45-53) and
`main()` entirely untested. No test file references `cli` anywhere under
`tests/` (`grep -rl "cli" tests/` returns nothing).

This is a real gap, not a stylistic nitpick: the CLI is the only place
that maps `PathSecurityError` to a rejection message and exit code 1, and
that maps `HealthStatus.connected` to the success/failure exit codes
described in the step's E2E validation. These behaviors are exactly the
kind of thin-but-load-bearing logic that regresses silently when nobody
is asserting on it, and later steps (e.g. `index`, `retrieve`, `query`
commands) will extend this file without a safety net unless it is
covered now.

## Actions

1. Add `tests/unit/test_cli.py` using `typer.testing.CliRunner`.
2. Cover `oneo health`:
   - exit code 0 and the "connected to database" message when the
     coordinator reports `HealthStatus(connected=True, ...)`.
   - exit code 1 and the "failed to connect" message when the
     coordinator reports `HealthStatus(connected=False, ...)`.
3. Cover `oneo files INPUT_PATH`:
   - prints each discovered path on its own line and exits 0 on success.
   - exit code 1 and a "rejected: ..." message when `discover()` raises
     `PathSecurityError`.
4. Use monkeypatching or dependency injection at the
   `oneo.cli._build_coordinator` seam (or an equivalent seam) so these
   tests do not require a live Neo4j instance or real filesystem
   traversal.
5. Re-run `uv run pytest --cov=oneo --cov-report=term-missing` and
   confirm `src/oneo/cli.py` coverage increases substantially (ideally
   at or near 100% of its non-trivial branches).
