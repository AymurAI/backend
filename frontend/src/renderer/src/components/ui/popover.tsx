import { css, cx } from "@/styled/css";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import type { ComponentPropsWithoutRef } from "react";

const Popover = PopoverPrimitive.Root;
const PopoverTrigger = PopoverPrimitive.Trigger;
const PopoverAnchor = PopoverPrimitive.Anchor;
const PopoverClose = PopoverPrimitive.Close;

const contentStyles = css({
  zIndex: 50,
  bg: "bg.primary",
  rounded: "lg",
  boxShadow: "[0px 0px 15px 0px #00000026]",

  "&[data-state='open']": {
    animation: "fadeIn",
  },
  "&[data-state='closed']": {
    animation: "fadeOut",
  },
});

const arrowStyles = css({
  fill: "bg.secondary",
});

function PopoverContent({
  className,
  sideOffset = 8,
  showArrow = false,
  container,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof PopoverPrimitive.Content> & {
  showArrow?: boolean;
  container?: HTMLElement;
}) {
  return (
    <PopoverPrimitive.Portal container={container}>
      <PopoverPrimitive.Content
        sideOffset={sideOffset}
        className={cx(contentStyles, className)}
        {...props}
      >
        {children}
        {showArrow && <PopoverPrimitive.Arrow className={arrowStyles} />}
      </PopoverPrimitive.Content>
    </PopoverPrimitive.Portal>
  );
}

export { Popover, PopoverAnchor, PopoverClose, PopoverContent, PopoverTrigger };
