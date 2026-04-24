import LoginLayout from "@/layout/login";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/home/_layout")({
  component: RouteComponent,
  onEnter: ({ context }) => context.queryClient.removeQueries(),
});

function RouteComponent() {
  return <LoginLayout />;
}
