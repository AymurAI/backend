import { useFiles } from "@/hooks";
import { Navigate, useParams } from "@tanstack/react-router";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export default function RequireFile({ children }: Props) {
  const files = useFiles();
  const { feature } = useParams({ from: "/$feature" });

  if (!files.length) {
    return <Navigate to="/$feature/onboarding" params={{ feature }} />;
  }

  return children;
}
