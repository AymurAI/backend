import { Card as BaseCard } from "@/components";
import { styled } from "@/styles";

/**
 * Styled card, containing step, image and description
 */
export const StyledCard = styled(BaseCard, {
  justifyContent: "center",
  alignItems: "center",
  textAlign: "center",
  gap: "$m",

  position: "relative",

  px: "$m",
  pt: "$l",
  pb: "$xl",
  maxWidth: 200,
  "@md": {
    pt: "$xxl",
    maxWidth: 160,
  },
  "@lg": {
    pt: "$l",
    maxWidth: 200,
  },
});

/**
 * Step indicator on Onboarding cards
 */
export const Step = styled("span", {
  bg: "$actionDefaultAlt",
  color: "$textOnButtonAlternative",

  position: "absolute",
  top: "$m",

  borderRadius: "100%",
  width: 36,
  height: 36,
  mb: "-$m",

  alignSelf: "end",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
});
