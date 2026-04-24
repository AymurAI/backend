import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/app/$feature/")({
  beforeLoad: ({ params }) => {
    throw redirect({
      to: "/app/$feature/onboarding",
      params: { feature: params.feature },
    });
  },
});
