import { Navigate, createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/home/")({
  component: Index,
});

function Index() {
  return <Navigate to="/home/host" />;
}
