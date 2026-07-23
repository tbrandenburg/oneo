> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# 13. Implementation

## Step 2.1 — CLI `--corpus` Flag Unit Test Coverage (gap-fill for Step 2)

### Objective

Close a test-coverage gap left by Step 2 ("Thread Corpus Through the
Pipeline"): every CLI command gained a `--corpus` option, and manual
verification (`oneo files --corpus engineering`,
`oneo validate --corpus billing --strict`, and rejecting an
out-of-root path with `--corpus billing`) confirms the option works
correctly end-to-end. However, `tests/unit/test_cli.py` never invokes
any command *with* the `--corpus` flag — every `_FakeCoordinator`
method accepts a `corpus` keyword, but no test asserts that Typer
actually parses `--corpus <name>` off the command line and forwards
that exact value to the coordinator call. This means a future refactor
of the CLI (e.g. converting per-command `--corpus` options into a
single Typer callback-level global option, as the step's own wording
"Add a global `--corpus` option" suggests but the implementation did
not literally do) could silently break corpus selection and no unit
test would catch it — only integration/E2E runs against a real
`corpuses.toml` would surface the regression.

### Implementation

1. In `tests/unit/test_cli.py`, extend `_FakeCoordinator` methods (or
   add a thin recording wrapper) to capture the `corpus` argument they
   were called with.
2. Add at least one unit test per corpus-aware command (`files`,
   `parse`, `validate`, `index`, `vector-search`, `retrieve`, `query`,
   `reset`, `verify`) that invokes it with `--corpus <name>` and
   asserts the fake coordinator received that exact corpus name.
3. Add a test that omits `--corpus` and asserts the coordinator is
   called with `corpus=None` (i.e. the CLI does not silently default
   to a hardcoded name; resolution is left to the registry as
   `pipeline.py` already implements).

### Do not implement

* Any change to the actual `--corpus` option wiring in `cli.py` unless
  a test written under this step reveals it is not correctly threaded
  (in which case fix only the exposed bug, not the surface area).

### End-to-end validation

Run `uv run pytest tests/unit/test_cli.py -q` and confirm the new
`--corpus`-threading tests pass alongside the existing suite.
