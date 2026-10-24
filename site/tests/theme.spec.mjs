import { test, expect } from "@playwright/test";

const base = "/2026-quant-competition/";

test("system is the default and tracks OS changes", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto(base);
  await expect(page.getByLabel("Appearance")).toHaveValue("system");
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(23, 27, 32)");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(246, 244, 239)");
});

test("explicit preferences survive reload and language navigation, then return to system", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto(base);
  await page.getByLabel("Appearance").selectOption("light");
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(246, 244, 239)");
  await page.reload();
  await expect(page.getByLabel("Appearance")).toHaveValue("light");
  await page.getByRole("link", { name: "简体中文", exact: true }).click();
  await expect(page.getByLabel("外观")).toHaveValue("light");
  await page.getByLabel("外观").selectOption("dark");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(23, 27, 32)");
  await page.reload();
  await expect(page.getByLabel("外观")).toHaveValue("dark");
  await page.getByLabel("外观").selectOption("system");
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(246, 244, 239)");
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(23, 27, 32)");
  await page.getByRole("link", { name: "English", exact: true }).click();
  await expect(page.getByLabel("Appearance")).toHaveValue("system");
});

test("invalid or unavailable storage still permits a usable theme selector", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("quant-lab-theme", "invalid"));
  await page.goto(base);
  await expect(page.getByLabel("Appearance")).toHaveValue("system");
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", { get() { throw new Error("Storage blocked"); } });
  });
  await page.reload();
  await page.getByLabel("Appearance").selectOption("dark");
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(23, 27, 32)");
});

test("without JavaScript the system palette remains readable", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, colorScheme: "dark" });
  const page = await context.newPage();
  await page.goto(`http://127.0.0.1:4397${base}`);
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(23, 27, 32)");
  await expect(page.locator("#theme-preference")).toBeHidden();
  await context.close();
});

for (const locale of ["en", "zh-CN"]) {
  for (const theme of ["light", "dark"]) {
    test(`${locale} ${theme}: text, tables and charts contrast; historical rows retained`, async ({ page }) => {
      await page.goto(locale === "en" ? `${base}docs/project/` : `${base}zh-CN/docs/project/`);
      await page.getByLabel(locale === "en" ? "Appearance" : "外观").selectOption(theme);
      await expect(page.locator("[data-result-id]")).toHaveCount(24);
      const measureContrast = () => {
        const rgb = value => value.match(/[\d.]+/g).slice(0, 3).map(Number);
        const luminance = value => rgb(value).map(c => {
          c /= 255;
          return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4;
        }).reduce((sum, c, i) => sum + c * [.2126, .7152, .0722][i], 0);
        const background = element => {
          for (let node = element; node; node = node.parentElement) {
            const color = getComputedStyle(node).backgroundColor;
            if (color !== "rgba(0, 0, 0, 0)") return color;
          }
          return "rgb(255, 255, 255)";
        };
        const contrast = (a, b) => {
          const values = [luminance(a), luminance(b)].sort((a, b) => b - a);
          return (values[0] + .05) / (values[1] + .05);
        };
        const problems = [];
        const selectors = ["body", ".intro", ".language a", ".theme-control", "select", ".button", ".pill", ".step-number", ".sample-values", ".results-table th", ".results-table td", ".result-status", ".status", ".research-card p", "pre", ".terminal-label"];
        for (const selector of selectors) for (const element of document.querySelectorAll(selector)) {
          if (!element.checkVisibility()) continue;
          const ratio = contrast(getComputedStyle(element).color, background(element));
          if (ratio < 4.5) problems.push(`${selector}: ${ratio.toFixed(2)}`);
        }
        for (const selector of [".sample-line", ".bid", ".ask"]) {
          const element = document.querySelector(selector);
          if (!element.checkVisibility()) continue;
          const style = getComputedStyle(element);
          const ratio = contrast(selector === ".sample-line" ? style.stroke : style.color, background(element));
          if (ratio < 3) problems.push(`${selector}: ${ratio.toFixed(2)}`);
        }
        return problems;
      };
      expect(await page.evaluate(measureContrast)).toEqual([]);
      await page.setViewportSize({ width: 390, height: 844 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.locator('label[for="path-crypto"]').click();
      await expect(page.locator(".panel-crypto")).toBeVisible();
      expect(await page.evaluate(measureContrast)).toEqual([]);
    });
  }
}
