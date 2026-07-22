> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-Fill Step 00302 — Populate Diagnostic Source Line Numbers

## Why this matters

Step 00300's suggested diagnostic schema includes a `line` field, and
action item 12 requires including "source positions where practical."
`Diagnostic.line` exists on the model (`src/oneo/models.py`), but nothing
in `src/oneo/validation.py` ever populates it — every diagnostic is
constructed without a `line` argument, so it is always `None`.

This is practical to fix without new parsing work: the loader
(`src/oneo/okf_loader.py::_extract_heading_blocks`) already computes each
heading's `start_line` while walking `markdown-it-py` tokens, so each
`OkfSection` (and therefore each `OkfLink`, which is built per-section)
has a natural line anchor available at parse time. Leaving `line` unset
means every diagnostic — including `unresolved-link`, `unresolved-anchor`,
`duplicate-section-id`, and `missing-required-field` — silently drops
useful source-position context that later steps (and human reviewers) may
come to rely on, especially once corpora grow beyond a handful of
documents where "which section" is not precise enough to eyeball a fix.

## Actions

1. Extend `OkfSection` (and/or `OkfLink`) in `src/oneo/models.py` to carry
   the section's/link's originating line number, sourced from the
   heading's `start_line` already computed in
   `okf_loader._extract_heading_blocks`.
2. Thread that line number through `OkfLoader._build_section` and
   `OkfLoader._build_links` so it is available on the parsed objects.
3. Update `src/oneo/validation.py` to pass `line=` on every `Diagnostic`
   construction where a source section/link is available
   (`_validate_required_fields`, `_validate_duplicate_section_ids`,
   `_validate_local_link`), and thread it through the frontmatter-level
   diagnostics as line `0`/`None` where no heading applies.
4. Update `src/oneo/cli.py`'s `validate` command to render the `line`
   field in its diagnostic output when present.
5. Add/extend unit tests in `tests/unit/test_validation.py` asserting that
   diagnostics for unresolved links/anchors and duplicate section IDs
   carry the correct, non-`None` line number.
6. Re-run `uv run pytest -q` and `uv run oneo validate ./knowledge
   --strict` to confirm no regressions and that line numbers appear in
   diagnostic output for a deliberately broken fixture corpus.
