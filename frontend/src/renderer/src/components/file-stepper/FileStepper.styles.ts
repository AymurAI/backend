import { Button as BaseButton } from "@/components";
import { styled } from "@/styles";

export const CaretButton = styled(BaseButton, {
  boxShadow: "4px 0px 4px rgba(0, 0, 0, 0.05)",

  // Marked as important because of Stitches hierarchy
  px: "0px !important",
  py: "$s !important",

  "&:disabled": {
    boxShadow: "none",
    color: "$textLighter",
  },
});

export const Carousel = styled("div", {
  display: "flex",
  flexDirection: "row",
  gap: "$s",
  alignItems: "center",
  wrap: "no-wrap",
  flex: 1,

  overflowX: "scroll",
});
