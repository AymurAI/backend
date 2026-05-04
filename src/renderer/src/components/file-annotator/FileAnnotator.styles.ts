import { styled } from "@/styles";

export const Container = styled("div", {
  flex: 1,
  minWidth: 0,
  // boxShadow: "0px 0px 10px rgba(0, 0, 0, 0.1)",

  zIndex: 1,
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
});

export const File = styled("div", {
  flex: 1,
  overflowY: "scroll",
  px: "$xl",
  pb: "$xl",
  // pt: "$l",

  "& p, & span, & em": {
    fontFamily: "$file",
    fontSize: 16,
    lineHeight: "160%",
  },
});

export const Paragraph = styled("p", {
  margin: "8px 0px",
});
