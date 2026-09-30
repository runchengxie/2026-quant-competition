# Public Repository Publication Audit — 2026-09-30

## Scope and disposition

The repository is now named `runchengxie/2026-quant-competition`. The user authorized English versions of the team reference documentation, asked to remove all three PDF release assets, and authorized publication after review. The repository remains private until the pull request and CI gates pass; visibility change and Pages deployment are the final release actions.

## Inventory and findings

| Surface | Coverage | Finding / disposition |
|---|---:|---|
| Reachable Git history | 46 commits and 114 tracked paths at initial inventory; a later scan covered 51 reachable commits | Screened reachable blobs for GitHub/OpenAI/AWS token shapes, private-key headers, and long credential assignments. No matches. This pattern scan is useful screening, not proof that no sensitive material exists. |
| Current local secrets | `.env.local` ignored and untracked; `.env.example` is a placeholder template | Keep local environment values outside Git. Recheck current and historical versions before publication. |
| GitHub release | `reference-pdfs-2026-09`; three PDF assets at audit start | All three assets were removed. A GitHub API verification returned an asset count of zero; the release title and notes now point to the English Markdown guides. |
| Markdown documentation | 36 Markdown files inventoried; 23 contained Chinese text | Translated to English. The market-data inventory was rewritten as a sanitized summary, removing local absolute paths and detailed account-permission probe data. |
| Pages source | `site/` allowlist | Contains only project introduction, high-level architecture, public competition dates and links, and a statement that verified results are not yet published. A recursive checker rejects nested/unlisted files, symlinks, and secret-like content. |

## Competition date reconciliation

| Material | Earlier discrepancy | Maintained source |
|---|---|---|
| Rules, README, schedule, and analysis | Earlier September–December schedule | Organizer's public rules dated 2026-09-23: registration closes 2026-10-23 23:59 HKT; trading runs 2026-10-26 00:00 through 2027-01-27 06:00 HKT. |
| Strategy and MVP notes | Historical wording could imply a final strategy selection | The English docs label the Hong Kong PIT and AIVIX U.S. ETF directions as research candidates; neither is stated as selected or registered. |

Source: [FundConnectHK public competition rules](https://fundconnecthk.com/quant-league/legal/competition-rules/).

## Remaining release gates

1. Preserve the verified zero-PDF-asset release state.
2. Review the final PR diff, all current tracked files, `.env.example`, and full history scan output without exposing credential values.
3. Pass locked dependency install, Ruff lint/format, pytest, compileall, full-history secret scan, and Pages content check in CI.
4. Confirm the Pages artifact contains only `site/` files.
5. Merge the reviewed PR, then change the repository to public and enable Pages; verify both URLs and workflow permissions.

No credential value, account identifier, raw holding, or raw provider response is recorded here.
