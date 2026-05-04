import { FeatureFlowEnum } from "@/types/features";
import { Database, Detective, type Icon } from "phosphor-react";

/**
 * AI Predict port
 */
export const PREDICT_PORT = 8899;

/**
 * Dataset Spreadsheet
 */
export const DATASET_URL =
  "https://docs.google.com/spreadsheets/d/1pzaGNM5BzRAOlj8p0NYtxnkU4VI_X5UcQsnIMOtLSVY/edit#gid=257379348";

/**
 * AymurAI API URL
 */
export const AYMURAI_API_URL = `http://localhost:${PREDICT_PORT}`;

export const FEATURE_ICON: Record<FeatureFlowEnum, Icon> = {
  [FeatureFlowEnum.Dataset]: Database,
  [FeatureFlowEnum.Anonymizer]: Detective,
};
