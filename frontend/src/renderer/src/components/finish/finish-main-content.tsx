import { SectionTitle } from "@/layout/section-title";
import { Grid, Stack, styled } from "@/styled/jsx";
import { type FeatureFlowEnum, featureNamespace } from "@/types/features";
import type React from "react";
import { useTranslation } from "react-i18next";
import MainContent from "../layout/main-content";
import Card from "../ui/card";

interface FinishMainContentProps {
  feature: FeatureFlowEnum;
  children: React.ReactNode;
}
export default function FinishMainContent({
  feature,
  children,
}: FinishMainContentProps) {
  const { t } = useTranslation(featureNamespace[feature]);
  return (
    <MainContent>
      <Stack gap={{ base: "4", xl: "10" }}>
        <Stack gap="4">
          <SectionTitle>{t("finish.sectionTitle")}</SectionTitle>
          <styled.h2 textStyle="paragraph.md.default" maxW="8/12">
            {t("finish.description")}
          </styled.h2>
        </Stack>
        <Card>
          <Stack gap={{ base: "4", xl: "8" }}>
            <styled.h2 textStyle="subtitle.md.default">{t("finish.subtitle")}</styled.h2>
            <Grid columns={4} gap="8" justifyContent="center" width="full">
              {children}
            </Grid>
          </Stack>
        </Card>
      </Stack>
    </MainContent>
  );
}
