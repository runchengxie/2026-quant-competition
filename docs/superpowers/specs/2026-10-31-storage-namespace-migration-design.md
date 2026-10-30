# Global market research data namespace migration

## Intent and scope

Make `DATA_ROOT/global-market-research` the canonical project data directory, matching the renamed source repository. Preserve all original inputs, evidence, consumed budgets and runtime safety checks. The user requested the rename and continued research; this design makes the migration scope reviewable before code or operational changes.

Global `DATA_ROOT` remains the workspace data root. Only this project's child directory changes. The private configuration directory name is not automatically renamed. Existing `competition.*` schemas, historical provider identities, publication hashes and experiment identifiers remain compatibility contracts.

## Observed constraints

At source baseline `2cef1038d9970aeba8adff85402e025fea0650e2`, acquisition, team dispatch, leaf-package paths, the Databento attempt guard and Gateway validation embed the old project child name. Reservations contain absolute owner/output paths and scientific source hashes. Existing source-path guards reject symlinks and junctions. Other research-owner records reference the historical name; they must not be bulk rewritten.

Machine inspection found three project scheduled tasks (Paper account snapshot, Paper settlement review and US CNN checkpoint) referencing the old location. Inventory also found many absolute links in retained pytest fixtures. No tasks, configurations, links, datasets or ledgers have been modified. Full private inventory belongs under project retention, not public Git.

## Approaches

1. Rename the directory and replace matching strings everywhere. Rejected: this changes historical records, risks losing guard/ledger identity and breaks absolute references and runtime environments.
2. Add an old-root junction. Rejected as the primary compatibility mechanism: active input and Gateway guards deliberately reject reparse paths. Those guards must remain intact.
3. Introduce explicit project-root configuration and migrate consumers first; move data only after rehearsed compatibility and cutover validation. Recommended. Historical identities remain unchanged, while a reviewed location mapping explains relocation.

## Phase A: Compatibility and rehearsal

- Add explicit project data-root selection for root tools and independently installed leaf packages. Honor an explicit project-root environment/configuration value; otherwise resolve the configured workspace `DATA_ROOT`. Existing installations that only have the legacy directory continue to select it. Fresh installations default to the new child name. If both old and new roots exist without an explicit selection, fail instead of guessing or merging them.
- Root and leaf packages must agree through configuration and versioned files; do not introduce cross-package Python imports. Keep `TeamConfig.data_root` meaning workspace root for v1. Introduce a versioned optional project-root configuration path rather than silently reinterpreting existing values. Final field names are builder choices documented in the implementation plan.
- Route all active storage decisions through the selected project root, including acquisition authorization markers, research reservations, ledgers, logs, retained results and environment defaults. Existing config/private deployment roots are not generalized without their own compatibility checks.
- A selected new path must not permit a second billable request or research attempt when a consumed marker exists under the legacy root. Cross-root guard reconciliation must fail closed on conflicting state. Test legacy-only, new-only, both roots, interrupted migration and output/code changes attempting to mint budget.
- Preserve historical artifact bytes. Where a consumer must interpret an old absolute location, use an explicit migration receipt mapping the exact old project root to the exact new root and preserved relative path. Apply mapping only at known location fields, never rewrite arbitrary content or infer owner identity from a folder name. Source, input, protocol and attempt hashes remain authoritative.
- Inventory scientific source-hash changes in leaf packages. A path-helper edit must not rebind an existing reservation or observation protocol. Old frozen studies use their retained source; new scientific work uses a new frozen protocol and source digest.
- Rehearse against synthetic copied fixtures, including hash-bound receipts and consumed markers. Historical reproducibility must not depend on an old-root junction. No production code may traverse an unknown reparse point.

## Phase B: Reviewable local cutover

Prepare a private cutover manifest listing exact absolute source/destination roots, regular-file counts/sizes and hashes, links and pointers, mutable configuration files, task action paths, runtime environments and downstream references. Bind every retained regular file's bytes before and after cutover; inventory output files need an explicit nonrecursive sealing rule. Inventory links separately without following them. The destination must be absent. Never delete or coalesce an existing destination.

The cutover may proceed only after all owners and active consumers are accounted for, current task states are rechecked, and there is a safe interval with no acquisition, research worker, broker session or checkpoint writing this tree. If a broker login, order, production scheduler semantic change or stop/restart of an unrelated service would be required, stop for that separately scoped action. Do not start a task or connect to a broker to validate path changes.

Verify the resolved source is exactly the configured legacy project directory and the resolved destination is exactly the selected new project directory, both direct children of the same configured data root. Use native PowerShell operations end-to-end. Move once on the same volume; retain a recovery receipt before mutation. Never use recursive deletion, shell-composed move commands, forced overwrites or global search/replace.

Update only inventoried mutable local path settings and the path portions of the three identified task actions, preserving triggers, enabled states, account/security context, trading settings and arguments unrelated to location. Export task/config recovery records privately first. This requested cutover includes those location updates only after the reviewed manifest confirms their scope.

Rebuild or individually verify moved runtime environments; Windows console launchers and editable installations can embed old absolute paths. Retained historical environments are evidence, not automatically valid operational environments. Never rewrite manifests to make a broken environment look reproduced.

Classify links without following them. Retain external/unknown targets unchanged and block dependent active consumers. Rebase only proven internal mutable location links with before/after receipts; preserve intentionally invalid historical test fixtures as historical evidence instead of silently repairing their test semantics. Do not claim every archived fixture is directly executable after relocation.

## Verification and recovery

Before enabling any new writes, verify authoritative hashes, manifest/receipt identity, selected roots across separately installed packages, acquisition/research guards, saved-output reproduction, read-only scheduled action construction and local path/ACL checks. No orders, paid downloads or scientific fits are needed for migration verification. Record unresolved downstream references and keep them blocked.

If validation fails, preserve both recovery metadata and failed-state evidence. Revert only the exact move and inventoried mutable path changes when safe; never copy two writable authorities or reset a consumed ledger. Shared publication pointers are not updated by migration tooling.

Tests and independent review precede PR merge. After merge, use stable main/release paths for local cutover, verify the new root and keep private retention records there. Clean only task-owned branches/worktrees. Directory rename completion and research-evidence acceptance are separate outcomes.

## Remaining research evidence

For the six evidence gaps, produce an owner-record crosswalk for the selected US study: requested claim, owner/source record, dated scope, input binding, present/missing/conflicting status and verification method. Source URLs and caller assertions alone never turn a gap into verified evidence. Establish trusted owner protocols and a separately frozen future holdout only when actual records support them. Do not buy data, invent historical timestamps, relabel exposed history or relax acceptance gates to close this task.
