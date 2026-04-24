import { styled } from "@/styles";

export const Layout = styled("main", {
  height: "100vh",

  display: "flex",
  flexDirection: "column",
});

export const Header = styled("header", {
  display: "flex",
  flexDirection: "row",
  justifyContent: "space-between",
  alignItems: "center",

  zIndex: 2,
  px: "$xl",
  py: "$l",
  gap: 10,

  bg: "$white",
  bb: "1px solid $borderPrimary",

  "@xl": {
    px: 150,
  },
});

export const Section = styled("section", {
  px: 40,
  py: "$xxl",
  flex: 1,

  display: "flex",
  flexDirection: "column",
  gap: "$m",

  bg: "$bgPrimary",
  "@xl": {
    px: 150,
  },
  variants: {
    spacing: {
      none: { gap: 0 },
      xxs: { gap: "$xxs" },
      xs: { gap: "$xs" },
      s: { gap: "$s" },
      m: { gap: "$m" },
      l: { gap: "$l" },
      xl: { gap: "$xl" },
      xxl: { gap: "$xxl" },
    },
  },
  defaultVariants: {
    spacing: "m",
  },
});

export const Footer = styled("nav", {
  display: "flex",
  flexDirection: "row",
  justifyContent: "flex-end",
  alignItems: "center",
  gap: "$m",

  zIndex: 1,

  py: "$l",
  px: 100,
  height: 100,

  bt: "1px solid $borderPrimary",

  bg: "$bgSecondary",
});
