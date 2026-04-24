import { styled } from "@/styles";

const Subtitle = styled("p", {
  variants: {
    size: {
      m: {
        fontSize: "$subtitleMd",
        lineHeight: "$subtitleMd",
      },
      s: {
        fontSize: "$subtitleSm",
        lineHeight: "$subtitleSm",
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
    textColor: {
      default: {
        color: "$textDefault",
      },
    },
  },
  defaultVariants: {
    size: "m",
    weight: "default",
    textColor: "default",
  },
});

export default Subtitle;
