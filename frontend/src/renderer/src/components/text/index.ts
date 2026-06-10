import { styled } from "@/styles";

const Text = styled("p", {
  variants: {
    size: {
      m: {
        fontSize: "$paragraphsMd",
        lineHeight: "$paragraphsMd",
      },
      s: {
        fontSize: "$paragraphsSm",
        lineHeight: "$paragraphsSm",
      },
      xs: {
        fontSize: "$paragraphsXsm",
        lineHeight: "$paragraphsXsm",
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

export default Text;
