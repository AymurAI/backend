import { styled } from "@/styles";

export const WrapperSearch = styled("div", {
  display: "flex",
  alignItems: "center",
  flexDirection: "row",
  gap: "$s",

  p: 12,
  height: 48,

  bg: "$bgSecondary",
  border: "1px solid $borderPrimary",
  borderRadius: "$xl",

  cursor: "text",

  "&:focus-within": {
    border: "1px solid $borderPrimaryAlt",
    boxShadow: "0px 2px 2px rgba(0, 0, 0, 0.16)",
  },
});

export const ContainerLabel = styled("div", {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "$s",
  width: "100%",
});

export const WrapperLabel = styled("div", {
  width: "100%",
});

export const WrapperSufixLabel = styled("div", {
  display: "flex",
  alignItems: "center",
  flexDirection: "row",
  gap: "$s",

  p: 12,
  height: 48,

  bg: "$bgSecondary",
  border: "1px solid $borderPrimary",

  cursor: "text",

  "&:focus-within": {
    border: "1px solid $borderPrimaryAlt",
    boxShadow: "0px 2px 2px rgba(0, 0, 0, 0.16)",
  },
});

export const InputContainer = styled("div", {
  display: "flex",
  alignItems: "center",
  gap: "$xxs",
  flex: 1,
});

export const Input = styled("input", {
  flex: 1,

  fontSize: "$labelMd",
  lineHeight: "$LabelMd",
  color: "$textDefault",

  p: 0,
  width: "$xxl",

  border: "none",
  outline: "none",
});

export const Counter = styled("div", {
  display: "flex",
  alignItems: "center",
  gap: "$xxs",
});

export const SuggestionContainer = styled("div", {
  display: "flex",
  gap: "$s",
});

export const Suggestion = styled("mark", {
  backgroundColor: "$bgSecondaryAlt",
  fontFamily: "$primary",
  padding: "0px $sizes$s",
  borderRadius: "$s",
  cursor: "pointer",
});
