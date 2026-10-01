import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://runchengxie.github.io",
  base: "/2026-quant-competition",
  output: "static",
  trailingSlash: "always",
  build: {
    inlineStylesheets: "never",
  },
  i18n: {
    locales: ["en", "zh-CN"],
    defaultLocale: "en",
    routing: {
      prefixDefaultLocale: false,
    },
  },
});
