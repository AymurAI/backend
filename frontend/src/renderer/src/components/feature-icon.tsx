import { cva } from "@/styled/css";
import { stack } from "@/styled/patterns";
import type { FeatureFlowEnum } from "@/types/features";
import { FEATURE_ICON } from "@/utils/config";
import type { Icon } from "phosphor-react";

const styles = cva({
  base: {
    ...stack.raw({ align: "center", justify: "center" }),
    p: "4",
    borderRadius: "[14px]",
  },
  variants: {
    disabled: {
      true: {
        bg: "bg.secondary",
        color: "text.lighter",
      },
      false: {
        color: "text.default",
        bg: "bg.primary-alternative",
      },
    },
    size: {
      lg: {
        width: "[70px]",
        height: "[70px]",
        p: "[14px]",
        rounded: "[14px]",
      },
      sm: {
        width: "10",
        height: "10",
        p: "2",
        rounded: "lg",
      },
    },
  },
  defaultVariants: {
    disabled: false,
    size: "lg",
  },
});

type FeatureIconProps = {
  size: "lg" | "sm";
  disabled?: boolean;
} & (
  | { feature: FeatureFlowEnum; icon?: never }
  | { feature?: never; icon: Icon }
);

export default function FeatureIcon({
  feature,
  size,
  icon: OverrideIcon,
  disabled = false,
}: FeatureIconProps) {
  const Icon = OverrideIcon ?? FEATURE_ICON[feature];
  return (
    <div className={styles({ disabled, size })}>
      <Icon size="100%" />
    </div>
  );
}
