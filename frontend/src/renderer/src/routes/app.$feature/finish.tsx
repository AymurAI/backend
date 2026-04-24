import { FinishAnonymizer, FinishDataset } from "@/components";
import { Feature } from "@/types/features";
import { createFileRoute, useParams } from "@tanstack/react-router";

export const Route = createFileRoute("/app/$feature/finish")({
  component: RouteComponent,
});

function RouteComponent() {
  const { feature } = useParams({ from: "/app/$feature/finish" });

  if (feature === Feature.Dataset) return <FinishDataset />;
  return <FinishAnonymizer />;
}
