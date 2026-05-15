export enum FeatureFlowEnum {
  Dataset = "DATA_SET",
  Anonymizer = "ANONYMIZER",
}

export const featureNamespace = {
  [FeatureFlowEnum.Dataset]: "dataset",
  [FeatureFlowEnum.Anonymizer]: "anonymizer",
} as const satisfies Record<FeatureFlowEnum, string>;

export const featureRouteSlug = {
  [FeatureFlowEnum.Dataset]: "data_set",
  [FeatureFlowEnum.Anonymizer]: "anonymizer",
} as const satisfies Record<FeatureFlowEnum, string>;

const FEATURE_BY_ROUTE_SLUG = Object.fromEntries(
  Object.entries(featureRouteSlug).map(([feature, slug]) => [slug, feature]),
) as Record<string, FeatureFlowEnum>;

export function parseFeatureRouteSlug(slug: string): FeatureFlowEnum | null {
  return FEATURE_BY_ROUTE_SLUG[slug.toLowerCase()] ?? null;
}

export function getFeatureRouteSlug(feature: FeatureFlowEnum): string {
  return featureRouteSlug[feature];
}
