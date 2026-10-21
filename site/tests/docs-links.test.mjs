import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { rewriteDocumentationLink } from "../remark-doc-links.mjs";

const source=fileURLToPath(new URL("../../docs/architecture.md",import.meta.url));
test("curated documents use localized site routes and preserve fragments",()=>{
  assert.equal(rewriteDocumentationLink("research/datasets.md#coverage",source),"/2026-quant-competition/docs/datasets/#coverage");
  assert.equal(rewriteDocumentationLink("research/datasets.zh-CN.md#coverage",source),"/2026-quant-competition/zh-CN/docs/datasets/#coverage");
});
test("uncurated sources stay GitHub links rather than becoming public routes",()=>{
  assert.equal(rewriteDocumentationLink("../README.md",source),"https://github.com/runchengxie/2026-quant-competition/blob/main/README.md");
  for(const url of ["#scope","https://example.org/x","/2026-quant-competition/#study"])
    assert.equal(rewriteDocumentationLink(url,source),url);
});
