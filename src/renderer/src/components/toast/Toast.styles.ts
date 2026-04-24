import { styled } from "@/styles";

export const Container = styled("div", {
  display: "flex",
  flexDirection: "row",
  alignItems: "center",
  alignSelf: "stretch",
  justifyContent: "space-between",

  p: "$m",

  borderRadius: "$xs",
  b: "1px solid $infoPrimary",

  variants: {
    isVisible: {
      true: {
        display: "flex",
      },
      false: {
        display: "none",
      },
    },
  },
});

export const Message = styled("div", {
  display: "flex",
  alignItems: "center",
  gap: "$s",
});

export const Close = styled("div", {
  display: "flex",
});
