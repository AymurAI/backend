import Suggestion from "@/components/ui/suggestion";
import { HStack, styled } from "@/styled/jsx";
import type { AllLabels, AllLabelsWithSufix } from "@/types/aymurai";
import type { ComponentPropsWithoutRef } from "react";

interface SuggestionLabelProps
  extends Omit<ComponentPropsWithoutRef<"mark">, "translate" | "color"> {
  isClickable?: boolean;
  children: string;
  label: AllLabels | AllLabelsWithSufix | undefined;
}
export default function SuggestionLabel({
  isClickable = false,
  label,
  children,
  ...props
}: SuggestionLabelProps) {
  return (
    <Suggestion clickable={isClickable} rounded {...props}>
      <HStack gap="2" alignItems="baseline" px="1">
        <styled.span m="0">{children}</styled.span>
        <styled.span
          m="0"
          color="black"
          textTransform="uppercase"
          textStyle="cta.md.strong"
          fontFamily="[Archivo !important]"
        >
          {label ?? "DESCONOCIDO"}
        </styled.span>
      </HStack>
    </Suggestion>
  );
}
