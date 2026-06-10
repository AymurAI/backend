import { cva, cx } from "@/styled/css";
import { styled } from "@/styled/jsx";
import { hstack } from "@/styled/patterns";
import type { Icon } from "phosphor-react";
import { Bell, X } from "phosphor-react";
import type { HTMLAttributes } from "react";

const calloutRecipe = cva({
  base: {
    ...hstack.raw({
      alignItems: "center",
      gap: "3",
    }),

    px: "4",
    py: "3",

    rounded: "sm",
    borderWidth: "[1px]",
    borderStyle: "solid",

    width: "full",

    textStyle: "paragraph.sm.default",
  },
  variants: {
    variant: {
      error: {
        bg: "system.error-secondary",
        borderColor: "system.error",
        color: "system.error",
      },
      warning: {
        bg: "system.warning-secondary",
        borderColor: "system.warning",
        color: "system.warning",
      },
      success: {
        bg: "system.success-secondary",
        borderColor: "system.success",
        color: "system.success",
      },
      info: {
        bg: "system.info-secondary",
        borderColor: "system.info",
        color: "text.default",
      },
    },
    noBorder: {
      true: {
        borderWidth: "0",
      },
    },
  },
  defaultVariants: {
    variant: "info",
    noBorder: false,
  },
});

export type CalloutVariant = "error" | "warning" | "success" | "info";

interface CalloutProps extends HTMLAttributes<HTMLDivElement> {
  message: string;
  variant?: CalloutVariant;
  noBorder?: boolean;
  onDismiss?: () => void;
  icon?: Icon;
}

function Callout({
  message,
  variant = "info",
  noBorder = false,
  onDismiss,
  icon: IconComponent = Bell,
  className,
  ...props
}: CalloutProps) {
  return (
    <div
      className={cx(calloutRecipe({ variant, noBorder }), className)}
      {...props}
    >
      <IconComponent
        size={20}
        weight="light"
        aria-hidden="true"
        style={{ flexShrink: 0 }}
      />
      <styled.span flex="1">{message}</styled.span>
      {onDismiss && (
        <styled.button
          type="button"
          aria-label="Dismiss notification"
          onClick={onDismiss}
          cursor="pointer"
        >
          <X size={18} aria-hidden="true" />
        </styled.button>
      )}
    </div>
  );
}

export default Callout;
