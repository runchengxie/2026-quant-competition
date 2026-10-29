# Research editorial refresh implementation plan

**Goal:** Make the research directory easier to browse and unify the home, market and CNN reading experience.

**Architecture:** Keep Astro and existing ECharts assets and evidence. Add progressive-enhancement category filters to the market directory and refine shared editorial presentation in both locales.

**Tech Stack:** Astro, CSS, browser JavaScript, Playwright.

## Steps

- [ ] Add browser tests for category filters, reset, keyboard operation, and the no-JavaScript directory.
- [ ] Implement localized, progressively enhanced filtering without changing research URLs.
- [ ] Refine home, directory and CNN styles for readable hierarchy, responsive layouts and both themes.
- [ ] Run site build, browser tests and review; publish through the repository workflow.
