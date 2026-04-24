import { Spinner } from "@/components";
import { CheckCircle, XCircle } from "phosphor-react";

import { colors } from "@/styles/tokens";

interface Props {
  hasError: boolean;
  isLoading: boolean;
}
export default function Icon({ hasError, isLoading }: Props) {
  if (hasError) return <XCircle size={48} color={colors.errorPrimary} />;
  if (isLoading) return <Spinner />;
  return <CheckCircle size={48} color={colors.primary} />;
}
