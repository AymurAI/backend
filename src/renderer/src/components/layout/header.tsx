import { useTutorialSeen } from "@/store/useLocal";
import { css } from "@/styled/css";
import { Divider, HStack, Stack, styled } from "@/styled/jsx";
import type { FeatureFlowEnum } from "@/types/features";
import { Link } from "@tanstack/react-router";
import FeaturesMenu from "../features-menu";
import HowItWorksModal from "../how-it-works-modal";

const header = css({
  position: "relative",
  width: "full",
  height: "24",
  py: "6",
  px: "12",
  bg: "bg.secondary",
  borderBottom: "[1px solid #BCBAB8]",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
});

const centerSlot = css({
  position: "absolute",
  left: "[50%]",
  transform: "translateX(-50%)",
});

interface HeaderProps {
  title?: string;
  center?: React.ReactNode;
  feature?: FeatureFlowEnum;
  right?: React.ReactNode;
}

export default function Header({ title, center, feature, right }: HeaderProps) {
  const tutorialSeen = useTutorialSeen(feature!);

  const img = title
    ? `${import.meta.env.BASE_URL}brand/aymurai-iso-darkpurple.svg`
    : `${import.meta.env.BASE_URL}brand/aymurai-hor-darkpurple.svg`;

  return (
    <header className={header}>
      <Link to="/home/features">
        <Stack gap="4" align="center" direction="row">
          <img height={40} src={img} alt="AymurAI logo" />
          {title && (
            <>
              <Divider
                orientation="vertical"
                thickness="[2px]"
                color="text.default"
                height="4"
              />
              <styled.span textStyle="subtitle.md.strong">{title}</styled.span>
            </>
          )}
        </Stack>
      </Link>
      {center && <div className={centerSlot}>{center}</div>}
      <HStack>
        {tutorialSeen && feature && <HowItWorksModal feature={feature} />}
        {right}
        <FeaturesMenu />
      </HStack>
    </header>
  );
}
