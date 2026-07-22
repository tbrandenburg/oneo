> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-Fill Step 00305 — Commit the Frontmatter Line-Offset Fix to Git

## Why this matters

Review of step 00304 (fix-diagnostic-line-number-frontmatter-offset)
found that the implementation is functionally complete and correct:
`_frontmatter_line_offset` in `src/oneo/okf_loader.py` correctly computes
and applies the frontmatter offset to `OkfSection.line`, the hardcoded
`line=0` in `_validate_required_fields` (`src/oneo/validation.py`) was
changed to `line=1`, the tests in `tests/unit/test_okf_loader.py` and
`tests/unit/test_validation.py` were updated/extended to assert against
true file line numbers (including a multi-line-frontmatter fixture), and
`uv run pytest -q` passes (50 passed). A manual E2E check with a fresh
fixture (8-line frontmatter block, heading on line 10, broken link)
confirmed `oneo validate --strict` reports `line=10`, matching
`grep -n "^# Doc"` on the actual file.

However, `git status` shows every one of these changes — the move of the
step file from `planned/` to `in-review/`, and the modifications to
`src/oneo/okf_loader.py`, `src/oneo/validation.py`,
`tests/unit/test_okf_loader.py`, and `tests/unit/test_validation.py` — as
uncommitted working-tree changes. `git log --oneline` shows no commit
for step 00304's work at all; the most recent commit is still step
00302's line-number population.

This is the exact same recurring failure mode already documented and
fixed three times before (gap-fill steps 00101, 00301, and 00303):
"implementing a step's code without committing it recurs across steps."
An uncommitted step is not durable or reproducible from a clean checkout
even if the working tree looks correct. Any subsequent step (00400 Neo4j
projection) would start from a tree silently missing the frontmatter
line-offset fix entirely, and diagnostics/sections would again report
body-relative rather than file-relative line numbers.

## Actions

1. Review `git status` and confirm exactly which files are step 00304's
   intended output (the frontmatter-offset fix in `okf_loader.py`, the
   `line=1` convention change in `validation.py`, and the corresponding
   test updates in `test_okf_loader.py` and `test_validation.py`) versus
   anything that should remain untracked.
2. Stage and commit all of the above in a single, logically-scoped
   commit (e.g. "Fix diagnostic line numbers for frontmatter offset (Step
   00304)").
3. Move `doc/plan/steps/in-review/00304-fix-diagnostic-line-number-frontmatter-offset.md`
   to `doc/plan/steps/closed/` as part of (or immediately after) this
   commit, consistent with how steps 00301 and 00303 closed out their
   predecessors.
4. Re-run `git status` after the commit and confirm the working tree is
   clean (no uncommitted modifications, no untracked files related to
   this step) before considering this gap closed.
5. Re-run `uv run pytest -q` after the commit to confirm the committed
   state still passes all tests (guards against a bad `git add`
   accidentally omitting a needed file).
