import { defineConfig } from "astro/config";
import documentationLinks from "./remark-doc-links.mjs";
import { unified } from "@astrojs/markdown-remark";

export default defineConfig({
  site: "https://runchengxie.github.io",
  base: "/2026-quant-competition",
  output: "static",
  trailingSlash: "always",
  markdown: { processor: unified({ remarkPlugins: [documentationLinks] }) },
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
