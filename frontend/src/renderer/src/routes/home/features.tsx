import BuiltBy from "@/components/brand/built-by";
import FeatureIcon from "@/components/feature-icon";
import Header from "@/components/layout/header";
import MainContent from "@/components/layout/main-content";
import Card from "@/components/ui/card";
import APIProtected from "@/features/APIProtected";
import { css } from "@/styled/css";
import { Grid, Stack, styled } from "@/styled/jsx";
import { FeatureFlowEnum } from "@/types/features";
import { FEATURE_ICON } from "@/utils/config";
import {
  Link,
  type LinkComponentProps,
  createFileRoute,
} from "@tanstack/react-router";
import type { Icon } from "phosphor-react";
import { useTranslation } from "react-i18next";

const builtBy = css({
  pos: "absolute",
  bottom: "16", // 64px
  left: "[50%]",
  transform: "[translateX(-50%)]",
});

interface CardToolProps extends LinkComponentProps {
  title: string;
  subtitle: string;
  icon: Icon;
  disabled?: boolean;
}
function CardTool({
  title,
  subtitle,
  icon: Icon,
  disabled = false,
  ...props
}: CardToolProps) {
  return (
    <Link disabled={disabled} {...props}>
      <Card className={css({ height: "full" })} clickable>
        <Stack align="start" gap="4">
          <FeatureIcon size="lg" icon={Icon} />
          <Stack gap="1">
            <styled.h2 textStyle="subtitle.md.strong">{title}</styled.h2>
            <styled.p textStyle="subtitle.sm.default" color="text.lighter">
              {subtitle}
            </styled.p>
          </Stack>
        </Stack>
      </Card>
    </Link>
  );
}

export const Route = createFileRoute("/home/features")({
  component: RouteComponent,
});

function RouteComponent() {
  const { t } = useTranslation(["common", "dataset", "anonymizer"]);

  return (
    <APIProtected>
      <Stack width="screen" height="screen" gap="0">
        <Header />
        <MainContent>
          <Stack gap="6">
            <styled.h1 textStyle="title.md.strong">
              {t("home.features.greeting")}
            </styled.h1>
            <Grid columns={2} rowGap="6" columnGap="6">
              <CardTool
                to="/$feature"
                params={{ feature: FeatureFlowEnum.Dataset }}
                title={t("dataset:title")}
                subtitle={t("dataset:subtitle")}
                icon={FEATURE_ICON.DATA_SET}
              />
              <CardTool
                to="/$feature"
                params={{ feature: FeatureFlowEnum.Anonymizer }}
                title={t("anonymizer:title")}
                subtitle={t("anonymizer:subtitle")}
                icon={FEATURE_ICON.ANONYMIZER}
              />
            </Grid>
          </Stack>
          {/* Floating content below */}
          <div className={builtBy}>
            <BuiltBy />
          </div>
        </MainContent>
      </Stack>
    </APIProtected>
  );
}
