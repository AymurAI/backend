import { cva, cx } from "@/styled/css";

const styles = cva({
  base: {
    transitionProperty: "[border, box-shadow]",
    transitionTimingFunction: "default",
    transitionDuration: "normal",
  },
  variants: {
    size: {
      lg: {
        p: "8",
        rounded: "sm",
      },
      sm: {
        rounded: "lg",
        p: "4",
      },
    },
    disabled: {
      true: {
        border: "primary",
        bg: "bg.primary",
        color: "text.lighter",
      },
      false: {
        border: "primary",
        bg: "bg.secondary",
      },
    },
    clickable: {
      true: {},
      false: {},
    },
  },
  compoundVariants: [
    {
      clickable: true,
      disabled: false,
      css: {
        cursor: "pointer",
        "&:hover": {
          border: "primary-alt",
          boxShadow: "[0px 0px 15px 0px #3F479D66]",
        },
      },
    },
    {
      clickable: true,
      disabled: true,
      css: {
        cursor: "not-allowed",
      },
    },
  ],
  defaultVariants: {
    disabled: false,
    clickable: false,
    size: "lg",
  },
});

interface CardProps {
  children?: React.ReactNode;
  disabled?: boolean;
  size?: "lg" | "sm";
  clickable?: boolean;
  className?: string;
}
export default function Card({
  disabled = false,
  size = "lg",
  clickable = false,
  children,
  className,
}: CardProps) {
  const classes = styles({ size, disabled, clickable });
  return <div className={cx(className, classes)}>{children}</div>;
}
