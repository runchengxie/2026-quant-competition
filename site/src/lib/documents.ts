import { Content as robustnessEn } from "../../../docs/research/strategy-robustness.md";
import { Content as predictiveEn } from "../../../docs/research/equity-predictive.md";
import { Content as predictiveZh } from "../../../docs/research/equity-predictive.zh-CN.md";
import { Content as incrementalEn } from "../../../docs/research/incremental-research.md";
import { Content as incrementalZh } from "../../../docs/research/incremental-research.zh-CN.md";
import { Content as comparisonEn } from "../../../docs/research/strategy-comparison.md";
import { Content as comparisonZh } from "../../../docs/research/strategy-comparison.zh-CN.md";
import { Content as robustnessZh } from "../../../docs/research/strategy-robustness.zh-CN.md";
import { Content as refreshEn } from "../../../docs/research/data-refresh.md";
import { Content as refreshZh } from "../../../docs/research/data-refresh.zh-CN.md";
import { Content as nativeEn } from "../../../docs/operations/native-process-diagnostics.md";
import { Content as nativeZh } from "../../../docs/operations/native-process-diagnostics.zh-CN.md";
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
import { Content as controlsEn } from "../../../docs/research/strategy-controls.md";
import { Content as controlsZh } from "../../../docs/research/strategy-controls.zh-CN.md";
import { Content as executionEn } from "../../../docs/research/us-execution-evidence.md";
import { Content as executionZh } from "../../../docs/research/us-execution-evidence.zh-CN.md";
import { Content as observationEn } from "../../../docs/research/observation-registry.md";
import { Content as observationZh } from "../../../docs/research/observation-registry.zh-CN.md";
import { Content as cnnEn } from "../../../docs/research/cnn-chart-research.md";
import { Content as cnnZh } from "../../../docs/research/cnn-chart-research.zh-CN.md";

const content={
  "cnn-chart-research.en":cnnEn,
  "cnn-chart-research.zh-CN":cnnZh,
  "strategy-comparison.en":comparisonEn,
  "strategy-comparison.zh-CN":comparisonZh,
  "incremental-research.en":incrementalEn,
  "incremental-research.zh-CN":incrementalZh,
  "equity-predictive.en":predictiveEn,
  "equity-predictive.zh-CN":predictiveZh,
  "strategy-robustness.en":robustnessEn,
  "strategy-robustness.zh-CN":robustnessZh,
  "data-refresh.en":refreshEn,
  "data-refresh.zh-CN":refreshZh,
  "native-process-diagnostics.en":nativeEn,
  "native-process-diagnostics.zh-CN":nativeZh,
  "architecture.en":architectureEn,"architecture.zh-CN":architectureZh,
  "quickstart.en":quickstartEn,"quickstart.zh-CN":quickstartZh,
  "datasets.en":datasetsEn,"datasets.zh-CN":datasetsZh,
  "study.en":studyEn,"study.zh-CN":studyZh,
  "strategies.en":strategiesEn,"strategies.zh-CN":strategiesZh,
  "strategy-controls.en":controlsEn,"strategy-controls.zh-CN":controlsZh,
  "execution-evidence.en":executionEn,"execution-evidence.zh-CN":executionZh,
  "observation-registry.en":observationEn,"observation-registry.zh-CN":observationZh,
};
export const documents=documentRoutes.map(doc=>({...doc,Content:content[`${doc.slug}.${doc.locale}` as keyof typeof content]}));
export type DocumentEntry=(typeof documents)[number];
