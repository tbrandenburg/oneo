> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Commit accumulated doc/plan/steps lifecycle moves and AGENTS.md lessons

## Why this matters

Step 00601 ("Commit Hybrid Retrieval to Git") successfully committed the
Step 6 source/test files in commit `bfa52d0` ("Implement hybrid
retrieval with rank fusion (Step 6 / Step 00600)"). However, that
commit's diff (`git show --stat bfa52d0`) contains only the ten
implementation/test files — it does **not** include:

* `AGENTS.md` — the working tree has 58 lines of uncommitted "Key
  pitfall" lessons (the "sixth time" recurrence for step 00500 and the
  "seventh time" recurrence for step 00600) that were never committed.
  `git log --oneline -- AGENTS.md` shows the last committed change was
  `d34bd07` (the "fifth time" lesson); everything after that is still
  only on disk.
* The doc/plan/steps lifecycle file moves that step 00601's own Action
  1 explicitly named as in-scope: `doc/plan/steps/closed/00305-...md`,
  `00400-...md`, `00401-...md`, `00402-...md`, `00403-...md`,
  `00500-...md`, `00501-...md`, and `00600-...md` are all untracked
  (`git status --short` shows them as `??`), while the corresponding
  files under `doc/plan/steps/planned/` (`00400-...`, `00500-...`,
  `00600-...`) are still tracked-but-deleted in the working tree. `git
  ls-tree -r HEAD --name-only | grep doc/plan/steps` confirms HEAD still
  thinks 00400/00500/00600 live in `planned/`, not `closed/`.

This is the uncommitted-step pitfall recurring again, this time at the
meta/documentation level rather than the source level: a `git clone` of
the current HEAD would show the plan's step tracker as if steps
00400/00500/00600 were still in `planned/`, and would be missing eight
lessons' worth of AGENTS.md guidance. This directly contradicts the
"reproducible from a clean checkout" and "durable audit trail"
requirements this exact class of gap-fill step exists to prevent.

## Actions

1. Run `git status --short` to confirm the exact set of stale/untracked
   `doc/plan/steps/` entries and the `AGENTS.md` modification listed
   above.
2. `git add` the AGENTS.md modification and all closed-step files:
   `doc/plan/steps/closed/00305-commit-diagnostic-frontmatter-offset-fix.md`,
   `doc/plan/steps/closed/00400-implement-the-neo4j-projection.md`,
   `doc/plan/steps/closed/00401-commit-neo4j-projection-to-git.md`,
   `doc/plan/steps/closed/00402-fix-links-to-target-anchor-warning.md`,
   `doc/plan/steps/closed/00403-commit-target-anchor-warning-fix.md`,
   `doc/plan/steps/closed/00500-add-embeddings.md`,
   `doc/plan/steps/closed/00501-commit-embeddings-to-git.md`,
   `doc/plan/steps/closed/00600-implement-hybrid-retrieval.md`,
   plus the deletions of the corresponding stale copies under
   `doc/plan/steps/planned/` (00400, 00500, 00600).
3. Also move (via `git mv` or add+rm) `doc/plan/steps/in-review/00601-commit-hybrid-retrieval-to-git.md`
   to `doc/plan/steps/closed/` once this gap-fill step and 00601 are
   both confirmed complete, and add the git-tracked move.
4. Commit with a message describing this catch-up
   (e.g. "Commit accumulated plan-lifecycle moves and AGENTS.md
   lessons (gap-fill 00602)").
5. Re-run `git status --short` after the commit and confirm no
   `doc/plan/steps/` or `AGENTS.md` entries remain modified/untracked.
6. As a process fix, add a note to AGENTS.md (or reinforce the existing
   lesson) that "commit before moving to in-review" must include *all*
   working-tree changes (`git add -A` scoped review), not just the
   source/test files named in a step's Action list — since this gap
   shows that even an explicit file list in a step description can
   still miss sibling housekeeping changes (AGENTS.md, doc/plan/steps
   moves) sitting in the same working tree.
</content>
