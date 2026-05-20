import { useFiles } from "@/hooks";
import { getFeatureRouteSlug, parseFeatureRouteSlug } from "@/types/features";
import { Navigate, useParams } from "@tanstack/react-router";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export default function RequireFile({ children }: Props) {
  const files = useFiles();
  const { feature: featureSlug } = useParams({ strict: false }) as { feature?: string };
  const feature = featureSlug ? parseFeatureRouteSlug(featureSlug) : null;

  if (!feature) return <Navigate to="/home/features" />;

  if (!files.length) {
    return <Navigate to="/$feature/onboarding" params={{ feature: getFeatureRouteSlug(feature) }} />;
  }

  return children;
}
