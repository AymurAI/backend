import { styled } from "@/styles";

export const Container = styled("label", {
  display: "flex",
  flexDirection: "column",
  gap: "$xs",

  fontWeight: 400,
  fontSize: "$labelSm",
  lineHeight: "$labelSm",

  color: "$textDefault",
});

export const InputContainer = styled("div", {
  display: "flex",
  flexDirection: "row",
  alignItems: "center",
  gap: "$s",
  flex: 1,

  p: 12,

  bg: "$bgSecondary",
  b: "1px solid $borderPrimary",
  borderRadius: "$xs",

  "&:focus": {
    outline: "none",
    b: "1px solid $borderPrimaryAlt",
    boxShadow: "0px 2px 2px rgba(0, 0, 0, 0.16)",
  },
});
export const Input = styled("input", {
  fontWeight: 400,
  fontSize: "$labelMd",
  lineHeight: "$labelMd",

  b: "none",
  outline: "none",

  flex: 1,
});
