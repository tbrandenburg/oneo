> Mandatory: read the overall plan in full before proceeding: doc/plan/plan.md

# Gap-fill — Actually Delete the Stray Root-Level `factory_v2.sh` Copy

## Why this matters

Step 00104 (remove-stray-untracked-factory-v2-copy) required deleting the
untracked, byte-identical `factory_v2.sh` copy at the repository root
(action 2) and re-confirming a clean `git status` (action 4). Its commit
`6abac09` ("Ignore stray factory_v2.sh at repo root (00104)") only added
`/factory_v2.sh` to `.gitignore` — the diff for that commit touches
`.gitignore` alone, one insertion — and the commit message's claim that it
"deletes the untracked byte-identical copy" is false.

On-disk verification during this review confirms the file is still
present at the repository root:

```
$ ls -la factory_v2.sh .factory/factory_v2.sh
-rwxr-xr-x 1 btr8fe btr8fe 31960 ... .factory/factory_v2.sh
-rwxr-xr-x 1 btr8fe btr8fe 31960 ... factory_v2.sh
$ diff factory_v2.sh .factory/factory_v2.sh
(no output — files are still identical)
```

The root copy's mtime is *newer* than the `.factory/` copy's, meaning it
was re-created (or never removed) after the relocation. Because
`/factory_v2.sh` is now gitignored, `git status --short` no longer shows
it, which makes the working tree *look* clean while a genuine stray file
still clutters the repo root — the exact false-clean-tree problem step
00104 was meant to eliminate, just one layer deeper (now hidden by
`.gitignore` instead of by a wrong commit message).

This must be closed out before later steps assume the root directory
only contains project-relevant files.

## Actions

1. Confirm `factory_v2.sh` at the repository root still exists and is
   byte-identical to `.factory/factory_v2.sh` (`diff factory_v2.sh
   .factory/factory_v2.sh` produces no output).
2. Delete the stray root-level `factory_v2.sh` file for real (`rm
   factory_v2.sh`), keeping only `.factory/factory_v2.sh` in the
   filesystem and under version control.
3. Investigate what is re-creating the root-level copy (e.g. an operator
   invoking `./factory_v2.sh` from the repo root instead of
   `./.factory/factory_v2.sh`, or a wrapper/alias that copies it there
   before running) and document or fix the root cause so the file does
   not reappear. If the recurrence is expected and unavoidable, note this
   explicitly rather than relying solely on `.gitignore` to hide it.
4. Re-run `ls factory_v2.sh` (expect "No such file or directory") and
   `git status --short` and confirm neither reports a stray
   `factory_v2.sh` at the root.
5. Commit the cleanup with a message that references this gap-fill step
   and does not overstate what was actually done (avoid repeating the
   inaccurate claim made in commit `6abac09`).
