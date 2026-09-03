# 2026 Competition Document Architecture Design

## Goal

Reorganize the competition knowledge base into clear source, competition, strategy, and operations sections while preserving all original source files and removing duplicated narrative from the two analysis documents.

## Decisions

- Keep original PDFs under `docs/sources/`.
- Put human-readable PDF conversions under `docs/operations/`.
- Make `competition-analysis.md` the competition/rules interpretation document.
- Make `strategy-analysis.md` the strategy design and Strategy Deck document.
- Use stable English filenames for moved and converted files.
- Update `README.md` to reflect the actual tree and reading order.
- Do not modify trading code, rules content, or source PDFs.

## Target Structure

```text
docs/
├── competition/
│   ├── rules.md
│   ├── competition-analysis.md
│   └── schedule-and-checklist.md
├── strategy/
│   ├── strategy-analysis.md
│   └── strategy-deck-outline.md
├── operations/
│   ├── ibkr-simulated-account-guide.md
│   └── team-token-guide.md
└── sources/
    ├── rules.pdf
    ├── ibkr-simulated-account-guide.pdf
    └── team-token-guide.pdf
```

## Content Boundaries

`competition-analysis.md` owns rules, account permissions, schedule, scoring, awards, and open questions. `strategy-analysis.md` owns strategy positioning, alpha, portfolio construction, validation, metrics, and deck structure. Repeated background should be replaced with cross-links.

## Acceptance Criteria

- No original PDF is lost.
- Every moved Markdown/PDF has a stable, descriptive filename.
- Both PDF conversions preserve headings, lists, tables where extractable, links, and page/source notes.
- README links resolve to the new locations.
- The old root-level analysis and PDF filenames no longer remain.
- Markdown files contain no accidental empty or binary extraction artifacts.
