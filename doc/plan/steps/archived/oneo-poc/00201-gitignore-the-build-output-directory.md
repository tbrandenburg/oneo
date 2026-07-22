# Gap-Fill Step 00201 — Gitignore the `build/` output directory

## Gap

Step 00200 introduced the `oneo parse ... --output build/corpus.json` CLI
command and documents `build/corpus.json` as the target of its own
end-to-end validation. Running that validation (exactly as instructed in
the step file) creates a `build/` directory containing a generated
corpus artifact, but `.gitignore` does not exclude `build/`. Since Neo4j
is meant to be the only derived store and the filesystem is the sole
canonical source, this generated artifact must not be a candidate for
accidental commit — it is reproducible output, not source of truth, and
committing it would create drift between the checked-in artifact and
what a fresh rebuild would produce.

This matters because a later `./scripts/demo.sh` step (00900/01000) is
also likely to write to `build/`, compounding the risk of accidental
commits of stale, non-reproducible output.

## Actions

1. Add a `build/` entry to `.gitignore`.
2. Verify with `git status` after running `oneo parse ./knowledge --output
   build/corpus.json` that `build/` no longer appears as untracked.
