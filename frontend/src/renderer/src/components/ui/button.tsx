import { type RecipeVariantProps, css, cva, cx } from "@/styled/css";
import { CircleNotch } from "phosphor-react";
import type { ButtonHTMLAttributes } from "react";

const button = cva({
  base: {
    display: "flex",
    flexDir: "row",
    gap: "1", // 4px
    justifyContent: "center",
    alignItems: "center",

    transitionProperty: "[background-color, color, box-shadow]",
    transitionDuration: "slow", // 300ms
    transitionTimingFunction: "default",

    border: "none",

    textStyle: "cta.md.strong",

    cursor: "pointer",

    "&:disabled": {
      cursor: "not-allowed",
    },
  },
  variants: {
    variant: {
      primary: {
        bg: "action.default",
        color: "text.onbutton-default",

        "&:hover:enabled": {
          bg: "action.hover",
          color: "text.onbutton-alternative",
        },

        "&:active:enabled": {
          bg: "action.pressed",
          color: "text.onbutton-alternative",
        },

        "&:focus:enabled": {
          bg: "action.focus",
          outline: "primary-alt",
          outlineWidth: "[2px]",
          boxShadow: "[0px 0px 10px rgba(17, 0, 65, 0.2)]",
        },

        "&:disabled": {
          bg: "action.disabled",
          color: "text.onbutton-default",
        },
      },
      secondary: {
        color: "text.onbutton-default",
        bg: "bg.secondary",

        borderWidth: "[2px]",
        borderStyle: "solid",
        borderColor: "action.alt-default",

        "&:hover:enabled": {
          color: "text.onbutton-default",
          bg: "bg.secondary",
          borderColor: "action.hover",
        },

        "&:active:enabled": {
          color: "text.onbutton-alternative",
          bg: "action.pressed",
          borderColor: "action.pressed",
        },

        "&:focus:enabled": {
          boxShadow: "[0px 0px 10px rgba(17, 0, 65, 0.2)]",
          outline: "primary-alt",
          outlineWidth: "[2px]",
          bg: "bg.secondary",
        },

        "&:disabled": {
          color: "text.onbutton-disabled",
          bg: "bg.secondary",
          borderColor: "action.disabled",
        },
      },
      tertiary: {
        // TODO: not implemented
      },
      none: {
        padding: "0",
        bg: "[inherit]",
      },
    },
    size: {
      md: { height: "12", padding: "4", rounded: "sm" },
      sm: { height: "9", py: "2", px: "4", rounded: "sm" },
      "icon-md": {
        height: "12",
        width: "12",
        padding: "3",
        rounded: "md",
      },
      "icon-sm": { height: "9", width: "9", padding: "2", rounded: "md" },
    },
    checked: {
      true: {
        bg: "action.pressed !important",
        color: "text.onbutton-alternative !important",
      },
      false: {},
    },
  },
  defaultVariants: {
    size: "md",
    variant: "primary",
    checked: false,
  },
});

type ButtonProps = RecipeVariantProps<typeof button> &
  ButtonHTMLAttributes<HTMLButtonElement> & {
    isLoading?: boolean;
  };

function Button({
  size,
  variant,
  isLoading,
  disabled,
  children,
  className,
  checked,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      className={cx(button({ size, variant, checked }), className)}
      disabled={disabled || isLoading}
    >
      {isLoading ? (
        <CircleNotch className={css({ animation: "spin" })} />
      ) : (
        children
      )}
    </button>
  );
}

export default Button;
