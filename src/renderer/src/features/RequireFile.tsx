import { useFiles } from "@/hooks";
import { Navigate, useParams } from "@tanstack/react-router";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export default function RequireFile({ children }: Props) {
  const files = useFiles();
  const { feature } = useParams({ from: "/app/$feature" });

  if (!files.length) {
    return <Navigate to="/app/$feature/onboarding" params={{ feature }} />;
  }

  return children;
}
