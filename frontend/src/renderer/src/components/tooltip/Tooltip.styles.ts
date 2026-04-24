import { styled } from "@/styles";

export const Message = styled("div", {
  display: "flex",
  flexDirection: "row",
  alignItems: "center",
  gap: "$s",
  whiteSpace: "nowrap",

  transition: "opacity $s ease",

  p: "$s",

  bg: "$bgPrimary",
  color: "$textDefault",

  boxShadow: "0px 4px 8px rgba(0, 0, 0, 0.1)",
  borderRadius: "$xs",
});

export const Tooltip = styled("div", {
  $$offset: "$sizes$s",

  display: "flex",
  flexDirection: "column",
  alignItems: "center",

  position: "absolute",
  top: "calc(100% + $$offset)",
  left: "50%",
  transform: "translateX(-50%)",
  zIndex: 1,

  // Adjust SVG Arrow position correctly
  mb: -1,
});

export const Wrapper = styled("div", {
  position: "relative",
  display: "inline-block",

  [`& ${Tooltip}`]: {
    visibility: "hidden",
    opacity: 0,
  },
  "&:focus-within, &:hover": {
    [`& ${Tooltip}`]: {
      visibility: "visible",
      opacity: 1,
    },
  },
});
