import { styled } from "@/styles";

export const PlusButton = styled("button", {
  boxShadow: "4px 0px 4px rgba(0, 0, 0, 0.05)",

  // Marked as important because of Stitches hierarchy
  px: "$s !important",
  py: "$s !important",
  // b: '2px solid $actionDefaultAlt',
  width: 48,
  height: 51,
  "&:disabled": {
    boxShadow: "none",
    color: "$textLighter",
  },
});
