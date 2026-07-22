> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-Fill Step 00304 — Fix Diagnostic Line Numbers to Reflect Actual File Position

## Why this matters

Review of step 00302 (populate-diagnostic-source-line-numbers) found that
the `line` values populated on `Diagnostic`/`OkfSection`/`OkfLink` are
computed relative to the Markdown *body* returned by
`frontmatter.loads(raw_text).content` (see
`OkfLoader.load`/`OkfLoader._build_sections` in
`src/oneo/okf_loader.py`), not relative to the raw source file on disk.
`python-frontmatter` strips the YAML frontmatter block before handing
`body` to `markdown-it-py`, so every `start_line`/`content_start_line`
token position is offset by however many lines the frontmatter block
(plus the blank separator line) actually occupies in the real file.

This was verified directly: for a fixture file whose real `# Intro`
heading is on line 7 (4-line frontmatter + `---` delimiters + blank
line), the populated `section.line` / diagnostic `line` was `1` — the
heading's position within the stripped body, not the file. This defeats
the entire purpose of the step (action item 12's "source positions where
practical" and the step's own stated goal of letting "later steps and
human reviewers... eyeball a fix"): a human or tool jumping to the
reported line in the actual `.md` file lands on the wrong line (often the
frontmatter block itself). The existing unit tests in
`tests/unit/test_validation.py` (`test_strict_mode_fails_on_unresolved_link`,
`test_strict_mode_fails_on_unresolved_anchor`) assert `diagnostic.line ==
1` for fixtures whose real heading line is 5 — the tests codify the bug
rather than catching it, because they never compare against the true
file line.

## Actions

1. In `OkfLoader.load` (`src/oneo/okf_loader.py`), compute the number of
   lines consumed by the frontmatter block (including its delimiters and
   any separating blank line) before handing `body` to `_build_sections`,
   and add that offset to every `start_line`/`content_start_line`
   computed in `_extract_heading_blocks` before it is stored on
   `OkfSection.line` (and propagated to `OkfLink.line` in
   `_build_links`). `python-frontmatter`'s `Post` object (or a manual
   scan of `raw_text` for the frontmatter delimiter positions) can supply
   this offset deterministically.
2. Update `_validate_required_fields` in `src/oneo/validation.py` if a
   more precise line (e.g. line 1, where the frontmatter block starts)
   is preferable to the current hardcoded `line=0` for missing-field
   diagnostics — confirm which convention the rest of the codebase
   expects and keep it consistent.
3. Update `tests/unit/test_validation.py` so the `line`-asserting tests
   use fixtures where the expected line number is computed against the
   *actual* file content (e.g. by counting lines up to the heading in the
   literal fixture string) rather than a body-relative guess, and add at
   least one fixture with a multi-line frontmatter block to prove the
   offset is applied correctly.
4. Add or extend a unit test in `tests/unit/test_okf_loader.py` asserting
   `OkfSection.line` matches the true 1-indexed file line of its heading
   for a fixture with non-trivial frontmatter.
5. Re-run `uv run pytest -q` and manually verify with a deliberately
   broken fixture corpus (frontmatter + broken link) that
   `uv run oneo validate <fixture-root> --strict` reports a `line` value
   matching the real line number when the fixture file is opened
   directly.
