import { Content as architectureEn } from "../../../docs/architecture.md";
import { Content as architectureZh } from "../../../docs/architecture.zh-CN.md";
import { Content as quickstartEn } from "../../../docs/operations/team-quickstart.md";
import { Content as quickstartZh } from "../../../docs/operations/team-quickstart.zh-CN.md";
import { Content as datasetsEn } from "../../../docs/research/datasets.md";
import { Content as datasetsZh } from "../../../docs/research/datasets.zh-CN.md";
import { Content as studyEn } from "../../../docs/research/real-data-study.md";
import { Content as studyZh } from "../../../docs/research/real-data-study.zh-CN.md";
import { Content as strategiesEn } from "../../../docs/research/strategies.md";
import { Content as strategiesZh } from "../../../docs/research/strategies.zh-CN.md";
import { documentRoutes } from "../../document-routes.mjs";

const content={
  "architecture.en":architectureEn,"architecture.zh-CN":architectureZh,
  "quickstart.en":quickstartEn,"quickstart.zh-CN":quickstartZh,
  "datasets.en":datasetsEn,"datasets.zh-CN":datasetsZh,
  "study.en":studyEn,"study.zh-CN":studyZh,
  "strategies.en":strategiesEn,"strategies.zh-CN":strategiesZh,
};
export const documents=documentRoutes.map(doc=>({...doc,Content:content[`${doc.slug}.${doc.locale}` as keyof typeof content]}));
export type DocumentEntry=(typeof documents)[number];
