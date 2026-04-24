import { Text } from "@/components";

import * as S from "./OnboardingCard.styles";

interface Props {
  step: number;
  text: string;
}
/**
 * @param step Current step, used to refer to an image on `/public`
 * @param text Text used to describe current step
 */
export function OnboardingCard({ step = 1, text }: Props) {
  return (
    <S.StyledCard>
      <S.Step>{step}</S.Step>
      <img
        src={`onboarding-steps/step${step}.png`}
        width="140"
        alt={`Step ${step}`}
      />
      <Text size="s">{text}</Text>
    </S.StyledCard>
  );
}
