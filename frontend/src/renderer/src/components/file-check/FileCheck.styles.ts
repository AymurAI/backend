import { styled } from "@/styles";

export const Wrapper = styled("div", {
  display: "flex",
  flexDirection: "column",
  flexWrap: "wrap",
  justifyContent: "center",
  alignItems: "center",
  gap: "$s",

  position: "relative",

  // Settings to enable ellipsis on file name
  maxWidth: 175,
  "& p": {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    width: "100%",
  },
});

export const Card = styled("div", {
  display: "flex",
  flexDirection: "column",
  flexWrap: "wrap",
  justifyContent: "center",
  alignItems: "center",

  height: 200,
  width: 150,

  borderWidth: "$sizes$xs",
  borderStyle: "solid",
  borderRadius: "$s",
  boxShadow: "0px 0px $sizes$xs rgba(0, 0, 0, 0.1)",

  variants: {
    hasError: {
      true: {
        bg: "$errorSecondary",
        borderColor: "$errorPrimary",
      },
      false: {
        bg: "$bgPrimary",
        borderColor: "$borderPrimary",
      },
    },
  },
  defaultVariants: {
    hasError: false,
  },
});
