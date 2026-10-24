export const documentRoutes = Object.entries({
  architecture: "docs/architecture",
  quickstart: "docs/operations/team-quickstart",
  datasets: "docs/research/datasets",
  study: "docs/research/real-data-study",
  strategies: "docs/research/strategies",
  "strategy-controls": "docs/research/strategy-controls",
  "strategy-robustness": "docs/research/strategy-robustness",
  "data-refresh": "docs/research/data-refresh",
  "native-process-diagnostics": "docs/operations/native-process-diagnostics",
  "execution-evidence": "docs/research/us-execution-evidence",
  "observation-registry": "docs/research/observation-registry",
  "equity-predictive": "docs/research/equity-predictive",
}).flatMap(([slug, source]) => ["en", "zh-CN"].map(locale => ({
  slug, locale, source: `${source}${locale === "zh-CN" ? ".zh-CN" : ""}.md`,
  route: `/2026-quant-competition/${locale === "zh-CN" ? "zh-CN/" : ""}docs/${slug}/`,
})));
