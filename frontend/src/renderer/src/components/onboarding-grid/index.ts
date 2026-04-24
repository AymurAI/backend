import { styled } from "@/styles";

export const OnboardingGrid = styled("div", {
  display: "grid",
  justifyItems: "center",
  gridTemplateColumns: "repeat(1, minmax(200px, 1fr))",
  gap: "$xl 0",

  "@md": {
    gridTemplateColumns: "repeat(4, minmax(160px, 1fr))",
  },
  "@xl": {
    gridTemplateColumns: "repeat(4, minmax(200px, 1fr))",
  },
});
