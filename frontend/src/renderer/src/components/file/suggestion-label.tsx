import Suggestion from "@/components/ui/suggestion";
import { css, cx } from "@/styled/css";
import { HStack, styled } from "@/styled/jsx";
import type { AllLabels, AllLabelsWithSufix } from "@/types/aymurai";
import { type ComponentPropsWithoutRef, forwardRef } from "react";

interface SuggestionLabelProps
  extends Omit<ComponentPropsWithoutRef<"mark">, "translate" | "color"> {
  isClickable?: boolean;
  isHighlighted?: boolean;
  isSearchMatch?: boolean;
  isSearchActive?: boolean;
  children: string;
  label: AllLabels | AllLabelsWithSufix | undefined;
}
const SuggestionLabel = forwardRef<HTMLElement, SuggestionLabelProps>(
  function SuggestionLabel(
    {
      isClickable = false,
      isHighlighted = false,
      isSearchMatch = false,
      isSearchActive = false,
      label,
      children,
      className,
      ...props
    },
    ref,
  ) {
    const stateClassName = css({
      ...(isHighlighted
        ? {
            outline: "[2px solid #3F479D]",
            outlineOffset: "[1px]",
            position: "relative",
            zIndex: "10",
          }
        : {}),
      ...(isSearchMatch
        ? {
            boxShadow: "[inset 0 -2px 0 #D89B00]",
            boxDecorationBreak: "clone",
          }
        : {}),
      ...(isSearchActive
        ? {
            boxShadow: "[inset 0 -3px 0 #D89B00]",
          }
        : {}),
    });

    const resolvedClassName = cx(stateClassName, className);

    const dataProps = isSearchMatch
      ? {
          "data-search-active": isSearchActive ? "true" : "false",
        }
      : {};

    return (
      <Suggestion
        ref={ref}
        clickable={isClickable}
        rounded
        className={resolvedClassName}
        {...dataProps}
        {...props}
      >
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
  },
);

export default SuggestionLabel;
