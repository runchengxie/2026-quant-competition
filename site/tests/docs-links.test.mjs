import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import {readFileSync} from "node:fs";
import { rewriteDocumentationLink } from "../remark-doc-links.mjs";
import {documentRoutes} from "../document-routes.mjs";

const source=fileURLToPath(new URL("../../docs/architecture.md",import.meta.url));
test("chart CNN research is reachable in both languages",()=>{
  for(const locale of ["en","zh-CN"]){
    const entry=documentRoutes.find(doc=>doc.slug==="cnn-chart-research"&&doc.locale===locale);
    assert.ok(entry,`CNN note for ${locale}`);
    assert.equal(rewriteDocumentationLink(`research/cnn-chart-research${locale==="zh-CN"?".zh-CN":""}.md`,source),entry.route);
  }
});
test("every curated document has a localized title and summary",()=>{
  for(const locale of ['en','zh-CN']){
    const catalog=JSON.parse(readFileSync(new URL(`../src/i18n/${locale}.json`,import.meta.url),'utf8')).documents;
    for(const doc of documentRoutes.filter(row=>row.locale===locale)){
      assert.ok(catalog.titles[doc.slug]?.trim(),`${locale} title for ${doc.slug}`);
      assert.ok(catalog.summaries[doc.slug]?.trim(),`${locale} summary for ${doc.slug}`);
    }
  }
});
test("curated documents use localized site routes and preserve fragments",()=>{
  assert.equal(rewriteDocumentationLink("research/datasets.md#coverage",source),"/2026-quant-competition/docs/datasets/#coverage");
  assert.equal(rewriteDocumentationLink("research/datasets.zh-CN.md#coverage",source),"/2026-quant-competition/zh-CN/docs/datasets/#coverage");
});
test("uncurated sources stay GitHub links rather than becoming public routes",()=>{
  assert.equal(rewriteDocumentationLink("../README.md",source),"https://github.com/runchengxie/2026-quant-competition/blob/main/README.md");
  for(const url of ["#scope","https://example.org/x","/2026-quant-competition/#study"])
    assert.equal(rewriteDocumentationLink(url,source),url);
});
