import { styled } from "@/styles";

export const BarContainer = styled("div", {
  height: "$m",
  width: "100%",

  bg: "$bgPrimary",
  borderRadius: "$xxs",

  overflow: "hidden",
});

export const Bar = styled("div", {
  width: "100%",
  height: "100%",

  backgroundSize: "$sizes$xl $sizes$xl",

  transition: "width $s ease",

  variants: {
    isCompleted: {
      true: {
        backgroundImage: `linear-gradient(
        135deg,
        $actionDefaultAlt 37.50%,
        $actionDefault 37.50%,
        $actionDefault 50%,
        $actionDefaultAlt 50%,
        $actionDefaultAlt 87.50%,
        $actionDefault 87.50%,
        $actionDefault 100%
      )`,
      },
      false: {
        backgroundImage: `linear-gradient(
        135deg,
        $actionDefault 37.50%,
        $actionDefaultAlt 37.50%,
        $actionDefaultAlt 50%,
        $actionDefault 50%,
        $actionDefault 87.50%,
        $actionDefaultAlt 87.50%,
        $actionDefaultAlt 100%
      )`,
      },
    },
  },
  defaultVariants: {
    isCompleted: false,
  },
});
