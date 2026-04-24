import { styled } from "@/styles";

const Label = styled("label", {
  variants: {
    size: {
      m: {
        fontSize: "$labelMd",
        lineHeight: "$labelMd",
      },
      s: {
        fontSize: "$labelSm",
        lineHeight: "$labelSm",
      },
    },
    weight: {
      default: {
        fontWeight: "$default",
      },
      strong: {
        fontWeight: "$strong",
      },
    },
    status: {
      default: {
        color: "$textLighter",
      },
      error: {
        color: "$errorPrimary",
      },
    },
  },
  defaultVariants: {
    size: "m",
    weight: "default",
    status: "default",
  },
});

export default Label;
