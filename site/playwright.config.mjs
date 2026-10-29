import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.mjs",
  outputDir: process.env.PAGES_TEST_OUTPUT || join(tmpdir(), "quant-competition-pages-tests"),
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:4397", browserName: "chromium" },
  webServer: {
    command: "npm run preview -- --host 127.0.0.1 --port 4397",
    url: "http://127.0.0.1:4397/global-market-research/",
    reuseExistingServer: false,
  },
});
