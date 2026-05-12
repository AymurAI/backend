import { SectionTitle } from "@/layout/section-title";
import { css } from "@/styled/css";
import { Grid, Stack, styled } from "@/styled/jsx";
import { hstack, stack } from "@/styled/patterns";
import { type FeatureFlowEnum, featureNamespace } from "@/types/features";
import { useTranslation } from "react-i18next";

const card = css({
  ...hstack.raw({ gap: "4", alignItems: "center" }),

  bg: "bg.secondary",
  border: "primary",
  rounded: "sm",

  px: "4",
  py: "6",

  "& > img": {
    width: "[200px]",
    height: "[130px]",
    objectFit: "contain",
    flexShrink: "0",
  },
});

const stepStyle = css({
  ...stack.raw({ align: "center", justify: "center" }),

  bg: "action.alt-default",
  color: "text.onbutton-alternative",
  rounded: "full",
  textStyle: "cta.md.strong",

  width: "9",
  height: "9",
});

interface CardProps {
  img: string;
  imgAlt: string;
  step: number;
  title: string;
  subtitle: string;
}
function Card({ img, imgAlt, step, title, subtitle }: CardProps) {
  return (
    <div className={card}>
      <img src={img} alt={imgAlt} />
      <Stack gap="4">
        <p className={stepStyle}>{step}</p>
        <Stack>
          <styled.h2 textStyle="paragraph.sm.strong">{title}</styled.h2>
          <styled.p textStyle="subtitle.sm.default">{subtitle}</styled.p>
        </Stack>
      </Stack>
    </div>
  );
}

interface HowItWorksProps {
  title?: React.ReactNode;
  feature: FeatureFlowEnum;
}
export default function HowItWorks({ title, feature }: HowItWorksProps) {
  const { t } = useTranslation();
  const { t: tFeature } = useTranslation(featureNamespace[feature]);

  const renderTitle =
    typeof title === "string" ? (
      <SectionTitle>{title}</SectionTitle>
    ) : (
      (title ?? <SectionTitle>{t("howItWorks")}</SectionTitle>)
    );

  return (
    <Stack gap="6">
      {renderTitle}
      <Grid columns={2}>
        <Card
          img={`${import.meta.env.BASE_URL}onboarding-steps/step1.png`}
          imgAlt={tFeature("howItWorks.step1.alt")}
          title={tFeature("howItWorks.step1.title")}
          subtitle={tFeature("howItWorks.step1.subtitle")}
          step={1}
        />
        <Card
          img={`${import.meta.env.BASE_URL}onboarding-steps/step2.png`}
          imgAlt={tFeature("howItWorks.step2.alt")}
          title={tFeature("howItWorks.step2.title")}
          subtitle={tFeature("howItWorks.step2.subtitle")}
          step={2}
        />
        <Card
          img={`${import.meta.env.BASE_URL}onboarding-steps/step3.png`}
          imgAlt={tFeature("howItWorks.step3.alt")}
          title={tFeature("howItWorks.step3.title")}
          subtitle={tFeature("howItWorks.step3.subtitle")}
          step={3}
        />
        <Card
          img={`${import.meta.env.BASE_URL}onboarding-steps/step4.png`}
          imgAlt={tFeature("howItWorks.step4.alt")}
          title={tFeature("howItWorks.step4.title")}
          subtitle={tFeature("howItWorks.step4.subtitle")}
          step={4}
        />
      </Grid>
    </Stack>
  );
}
