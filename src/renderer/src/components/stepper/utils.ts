import type { ParsedLocation } from "@tanstack/react-router";

const ROUTE_STEPS = {
  preview: 1,
  process: 2,
  validation: 3,
  finish: 4,
} as const;

type RouteSegment = keyof typeof ROUTE_STEPS;
type StepNumber = (typeof ROUTE_STEPS)[RouteSegment] | 0;

export const getStep = (location: ParsedLocation): StepNumber => {
  // Extract the last segment of the pathname
  // For routes like /app/$feature/preview, this gets 'preview'
  const segments = location.pathname.split("/").filter(Boolean);
  const lastSegment = segments.at(-1);

  if (!lastSegment) return 0;

  // Type-safe check: only return step if lastSegment is a valid RouteSegment
  if (isValidRouteSegment(lastSegment)) {
    return ROUTE_STEPS[lastSegment];
  }

  return 0;
};

// Type guard to check if a string is a valid route segment
function isValidRouteSegment(segment: string): segment is RouteSegment {
  return segment in ROUTE_STEPS;
}
