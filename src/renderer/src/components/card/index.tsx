import { styled } from "@/styles";

const Card = styled("div", {
  display: "flex",
  flexDirection: "column",
  alignItems: "flex-start",
  gap: "$xl",

  p: "$xl",

  bg: "$bgSecondary",
  b: "1px solid $borderPrimary",
  borderRadius: "$xxs",
  boxShadow: "0px 4px 20px rgba(0, 0, 0, 0.05)",
});

export default Card;
