# Remove Historical PDF Blobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the three original team reference PDFs from writable GitHub history and prepare GitHub Support cleanup for protected pull-request refs and cached copies, while preserving all non-PDF repository content and the asset-free release.

**Architecture:** Rewrite the public repository in a fresh mirror clone with `git-filter-repo`, filtering only the verified PDF paths. Preserve a private local bundle as a rollback point, validate the rewritten tree and refs, then atomically force-update only `main` and the existing release tag with explicit expected old object IDs. GitHub's protected `refs/pull/*` cannot be pushed; after the rewrite, prepare a Support request for their removal and for cached views, then verify the result before claiming full removal.

**Tech Stack:** Git, GitHub CLI, `git-filter-repo`, PowerShell.

**Spec:** User authorized historical PDF removal and was informed that this requires rewriting public history and force-pushing, which changes commit IDs.

## Global Constraints

- The public repository is `runchengxie/2026-quant-competition`.
- Preserve every non-PDF file and the public release `reference-pdfs-2026-09`; its asset list is currently empty.
- Filter only `docs/sources/ibkr-simulated-account-guide.pdf`, `docs/sources/rules.pdf`, `docs/sources/team-token-guide.pdf`, and the earlier path `rules.pdf` for the rules PDF.
- Never print or copy credentials, account details, or PDF contents into the procedure or logs.
- Rewrite only remote `main` and `refs/tags/reference-pdfs-2026-09`; abort if additional public branches/tags appear or if the expected old ref IDs change at any pre-push check.
- The mirror currently advertises 16 protected `refs/pull/*`; 10 PR heads have one or more PDFs in their current tree. Do not try to force-update these refs. Record affected PR numbers and wait for GitHub Support cleanup before declaring repository-wide removal complete.
- Keep a private local rollback bundle outside the public repository until verification is complete. Never push backup refs or the bundle.
- State clearly that forks, old clones, GitHub cached pages, or cached raw-file URLs may retain copies after the rewrite.

## Review Focus

- An unlisted branch or tag could still make an old PDF reachable; enumerate direct branch/tag refs immediately before migration and abort on unexpected refs.
- GitHub pull-request refs are provider-controlled and currently retain the PDFs; include the affected PRs in the post-rewrite Support request and verify cleanup afterward.
- The release tag could continue pointing at old history; rewrite and verify the tag along with `main`.
- A path typo could leave one historic PDF blob; search every rewritten reachable object for all four path spellings.
- A rewrite could alter unrelated file content; compare the old and new main trees after excluding only the four filtered paths.
- A concurrent push could be overwritten; use explicit `--force-with-lease` expectations captured immediately before the push.

## Execution status — 2026-10-01

- Rewrote and atomically pushed `main` (`7ab35b4d00b702e2d0d07247a94649e4f9d01c3a`) and `reference-pdfs-2026-09` (`0a4f145c839455698868a6111fb5386001090f65`). Follow-up audit commits are on `main`.
- Compared all 63 old commits to their rewritten trees; only the four PDF paths were removed, and one root commit containing only `rules.pdf` became empty.
- Default-branch raw PDF URLs return 404 and the release has zero assets.
- GitHub retains 16 protected pull-request refs; 10 PR head trees contain PDFs. Sample raw URLs through PR refs still return HTTP 200. Full removal is pending GitHub Support; the request is drafted locally and has not been sent.
- A complete pre-rewrite bundle of all 19 fetched refs (main, release tag, and 16 pull refs) is stored outside the public repository.

---

### Task 1: Freeze and back up public refs

**Files:**
- No repository source files.
- Create a local Git bundle outside the checkout in a private backup directory outside the repository.

**Interfaces:**
- Consumes: advertised refs from `origin` and the current local checkout.
- Produces: recorded pre-rewrite `main` and release-tag object IDs; a private bundle containing all current remote refs.

- [x] Run `git ls-remote --refs --heads --tags origin` and confirm the public remote advertises only the direct refs `refs/heads/main` and `refs/tags/reference-pdfs-2026-09`; the mirror also contains 16 protected `refs/pull/*/head` refs.
- [x] Record both old object IDs and the current release URL; confirm the release has zero assets.
- [x] Create and verify private bundles outside the repository, including a complete bundle of all 19 fetched refs. Do not upload them or add backup refs to GitHub.

### Task 2: Rewrite in a fresh mirror clone

**Files:**
- Modify after verification: `docs/operations/publication-audit-2026-09-30.md`.
- Create: disposable mirror clone outside the user checkout.
- Do not modify the main working checkout during filtering.

**Interfaces:**
- Consumes: the verified remote refs and the four historical path spellings.
- Produces: rewritten `main` and release tag, with all other file history preserved.

- [x] Clone `origin` with `--mirror` into a new migration directory and confirm refs match Task 1.
- [x] Run `git-filter-repo --sensitive-data-removal --invert-paths` for `docs/sources/ibkr-simulated-account-guide.pdf`, `docs/sources/rules.pdf`, `docs/sources/team-token-guide.pdf`, and `rules.pdf`.
- [x] Confirm the migration clone's `origin` URL before pushing.
- [x] Record the rewritten `main` and tag object IDs.

### Task 3: Validate the rewritten history

**Files:**
- No repository source files.

**Interfaces:**
- Consumes: original bundle and rewritten mirror clone.
- Produces: a validation record proving that only requested PDF paths were removed and that both refs are clean.

- [x] Confirm `git rev-list --objects --all` in the rewritten clone contains none of the four PDF paths, including rewritten pull-request refs; record 16 changed protected `refs/pull/*` refs.
- [x] Use `filter-repo/commit-map` to compare every original commit tree with its mapped rewritten commit tree, excluding only the four filtered paths; no other tree differences were found. The one omitted root commit contained only `rules.pdf`.
- [x] Confirm the existing release tag resolves to rewritten history without PDF blobs and that its release has zero assets.
- [x] Verify rewritten `main` and tag differ from their original IDs.
- [x] Review the exact refs and old/new IDs before the remote write.

### Task 4: Update the public refs and verify

**Files:**
- Modify remote ref: `refs/heads/main`.
- Modify remote ref: `refs/tags/reference-pdfs-2026-09`.

**Interfaces:**
- Consumes: validated mirror clone and the old ref IDs from Task 1.
- Produces: public `main` and release tag that no longer reference the PDFs.

- [x] Immediately before pushing, confirm the complete direct branch/tag ref set and both IDs still matched Task 1.
- [x] Push only rewritten `main` and tag, with explicit leases in one atomic push.
- [x] Fetch public refs into the user checkout and verify the new `main` and tag IDs.
- [x] Confirm the release still exists with zero assets; the four default-branch raw URLs return 404. Representative PR raw URLs still return 200 because protected PR refs remain.
- [x] Leave protected PR refs and any cached copies as-is. The user confirmed with the competition organizer that these materials were permitted to be public and explicitly directed that the remaining history be left alone. No Support request was sent.
- [x] Update the publication audit with rewritten IDs, tree validation, release assets, and raw URL observations.
- [x] Confirm the user checkout is clean on rewritten `main`; stale public branches/worktrees were not recreated.

## Final disposition — 2026-10-02

The requested cleanup of the writable main and release tag is complete. Protected PR refs containing the PDFs are intentionally retained under the user's organizer-confirmed authorization. The private backup and unsent Support draft are retained outside this repository; no external contact is pending.
