> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Remove Stray Untracked `factory_v2.sh` Copy Left at Repo Root

## Why this matters

Step 00103 (remove-stray-tooling-files-from-repo) committed
`git mv factory_v2.sh .factory/factory_v2.sh` in commit `2cb0c9f`, and
`git log --all -- factory_v2.sh` confirms the rename was recorded
correctly (the file only exists at `.factory/factory_v2.sh` in the
commit tree). However, on-disk verification during review found a
second, **untracked**, byte-for-byte identical copy of the file still
sitting at the repository root:

```
$ git status --short
?? factory_v2.sh
$ diff factory_v2.sh .factory/factory_v2.sh
(no output — files are identical)
```

Step 00103's action 3 required re-running `git status` after the change
"to confirm the working tree is clean," but the working tree is not
clean: an untracked `factory_v2.sh` reappeared at the root, defeating
the purpose of the relocation (a future `git add -A` or careless commit
would silently reintroduce the stray file at root). This is exactly the
class of clutter step 00103 was created to eliminate, so it must be
closed out before later steps build on top of an apparently-clean but
actually-dirty working tree.

## Actions

1. Confirm `factory_v2.sh` at the repository root is untracked
   (`git status --short` shows `?? factory_v2.sh`) and is byte-identical
   to `.factory/factory_v2.sh` (`diff factory_v2.sh .factory/factory_v2.sh`
   produces no output).
2. Delete the stray root-level `factory_v2.sh` copy, keeping only
   `.factory/factory_v2.sh` under version control.
3. Investigate why the copy reappeared (e.g. a wrapper script, the
   factory tooling itself, or an editor/agent process re-writing it to
   the root while running from the repo root) and, if it is expected to
   recur, add `/factory_v2.sh` to `.gitignore` as a defensive measure so
   it cannot be accidentally re-added, in addition to deleting the
   current stray copy.
4. Re-run `git status` and confirm it reports no untracked or modified
   files attributable to `factory_v2.sh`.
5. Commit the cleanup with a message that references this gap-fill step.
