import { type RecipeVariantProps, css, cx } from "@/styled/css";
import { Link as TanstackLink, type LinkProps as TanstackLinkProps } from "@tanstack/react-router";
import { CircleNotch } from "phosphor-react";
import { button } from "./button";

type LinkProps = RecipeVariantProps<typeof button> &
  TanstackLinkProps & {
    isLoading?: boolean;
    className?: string;
  };

export default function Link({
  size,
  variant,
  checked,
  isLoading,
  children,
  className,
  ...props
}: LinkProps) {
  return (
    <TanstackLink
      {...props}
      className={cx(button({ size, variant, checked }), className)}
    >
      {isLoading ? (
        <CircleNotch className={css({ animation: "spin" })} />
      ) : (
        children
      )}
    </TanstackLink>
  );
}
