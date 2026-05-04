import Loading from "@/layout/loading";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

export const Route = createFileRoute("/")({
  component: RouteComponent,
});

const TIMING = 2000;
function RouteComponent() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate({ to: "/home" });
    }, TIMING);

    return () => clearTimeout(timer);
  }, [navigate]);

  return <Loading />;
}
