import { css, cx } from "@/styled/css";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ComponentPropsWithoutRef } from "react";

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;

const contentStyles = css({
  zIndex: 50,
  bg: "bg.primary",
  rounded: "md",
  boxShadow: "[0px 0px 15px 0px #00000026]",

  "&[data-state='delayed-open']": {
    animation: "fadeIn",
  },
  "&[data-state='closed']": {
    animation: "fadeOut",
  },
});

const arrowStyles = css({
  fill: "bg.primary",
});

function TooltipContent({
  className,
  sideOffset = 6,
  showArrow = true,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof TooltipPrimitive.Content> & {
  showArrow?: boolean;
}) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={sideOffset}
        className={cx(contentStyles, className)}
        {...props}
      >
        {children}
        {showArrow && <TooltipPrimitive.Arrow className={arrowStyles} />}
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  );
}

export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger };
