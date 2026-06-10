import api from "@/services/api";
import { Navigate } from "@tanstack/react-router";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export default function APIProtected({ children }: Props) {
  if (!api.defaults.baseURL) return <Navigate to="/" />;
  return children;
}
