import { styled } from "@/styles";

// ----------------
// TEXT
// ----------------
export const TextContainer = styled("div", {
  display: "flex",
  flexDirection: "column",
  gap: "$xs",

  fontWeight: 400,
  fontSize: "$labelSm",
  lineHeight: "$labelSm",

  color: "$textDefault",

  cursor: "pointer",
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
});

export const Input = styled("input", {
  flex: 1,

  fontWeight: 400,
  fontSize: "$labelMd",
  lineHeight: "$labelMd",

  color: "$textDefault",

  cursor: "text",

  outline: "none",
  b: "none",
});

// ----------------
// OPTIONS
// ----------------
export const Option = styled("li", {
  p: "$m",
  width: "100%",

  listStyle: "none",

  fontWeight: "$default",
  fontSize: "$labelMd",
  lineHeight: "$labelMd",
  color: "$textDefault",

  cursor: "pointer",

  "&:hover, &:focus": {
    bg: "$primaryAlt",
    outline: "none",
  },
});

export const OptionContainer = styled("ul", {
  position: "absolute",
  zIndex: 2,

  minWidth: "100%",
  maxHeight: 200,
  minHeight: "$m",
  mt: "$m",
  overflowY: "scroll",

  display: "flex",
  flexDirection: "column",
  alignItems: "center",

  transitionDuration: "$transitions$s",
  transitionProperty: "opacity, visibility",
  transitionTimingFunction: "ease-in-out",

  bg: "$white",
  boxShadow: "0px $sizes$m $sizes$m rgba(0, 0, 0, 0.08)",
  borderRadius: "$xs",
});

export const Container = styled("div", {
  position: "relative",
  [`& ${OptionContainer}`]: {
    opacity: 0,
    visibility: "hidden",
  },
  "&:focus-within": {
    [`& ${OptionContainer}`]: {
      opacity: 1,
      visibility: "visible",
    },
    [`& ${InputContainer}`]: {
      outline: "1px solid $borderPrimaryAlt",
      boxShadow: "0px 2px 2px rgba(0, 0, 0, 0.16)",
      borderRadius: "$xs",
    },
  },
});
