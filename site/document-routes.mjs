export const documentRoutes = Object.entries({
  architecture: "docs/architecture",
  quickstart: "docs/operations/team-quickstart",
  datasets: "docs/research/datasets",
  study: "docs/research/real-data-study",
}).flatMap(([slug, source]) => ["en", "zh-CN"].map(locale => ({
  slug, locale, source: `${source}${locale === "zh-CN" ? ".zh-CN" : ""}.md`,
  route: `/2026-quant-competition/${locale === "zh-CN" ? "zh-CN/" : ""}docs/${slug}/`,
})));
