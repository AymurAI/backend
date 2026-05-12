import {
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";

import DropArea from "@/components/drop-area";
import HiddenInput from "@/components/hidden-input";
import HowItWorks from "@/components/how-it-works";
import Footer from "@/components/layout/footer";
import Header from "@/components/layout/header";
import HomeButton from "@/components/layout/home-button";
import MainContent from "@/components/layout/main-content";
import BackButton from "@/components/ui/back-button";
import Button from "@/components/ui/button";
import { useFileDispatch } from "@/hooks";
import { SectionTitle } from "@/layout/section-title";
import { addFiles } from "@/reducers/file/actions";
import { useSetTutorialSeen, useTutorialSeen } from "@/store/useLocal";
import { HStack, Stack, styled } from "@/styled/jsx";
import { featureNamespace } from "@/types/features";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

// FIRST step of the processing workflow
export const Route = createFileRoute("/app/$feature/onboarding")({
  component: RouteComponent,
});

function RouteComponent() {
  const queryClient = useQueryClient();
  const { feature } = useParams({
    from: "/app/$feature/onboarding",
  });
  const navigate = useNavigate();
  const { t } = useTranslation(featureNamespace[feature]);

  const inputRef = useRef<HTMLInputElement>(null);

  const dispatch = useFileDispatch();
  const tutorialSeen = useTutorialSeen(feature);
  const toggleTutorialSeen = useSetTutorialSeen();

  const handleAddFiles = async (files: File[]) => {
    dispatch(addFiles(files));
    await navigate({
      to: "/app/$feature/preview",
      params: { feature },
    });
    toggleTutorialSeen(feature);
  };

  const handleInputChange: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    const rawFiles = e.target.files;
    if (rawFiles) handleAddFiles(Array.from(rawFiles));
  };

  const handleOpenInput = () => {
    inputRef.current?.click();
  };

  useEffect(() => {
    queryClient.removeQueries({ queryKey: ["predict"] });
    queryClient.removeQueries({ queryKey: ["file-parser"] });
  }, []);

  return (
    <>
      <Header title={t("title")} feature={feature} right={<HomeButton />} />
      <MainContent>
        {tutorialSeen ? (
          <Stack gap="8">
            <HStack alignItems="center" gap="6">
              <BackButton to="/home/features" />
              <SectionTitle>{t("onboarding.sectionTitle")}</SectionTitle>
            </HStack>
            <DropArea
              title={t("onboarding.dropAreaTitle")}
              description={t("onboarding.dropAreaFormats")}
              onDropFiles={handleAddFiles}
            />
          </Stack>
        ) : (
          <HowItWorks feature={feature} />
        )}
      </MainContent>
      <Footer withBuiltBy>
        <HStack gap="4">
          {!tutorialSeen && (
            <styled.p textStyle="paragraph.sm.default">
              {t("onboarding.validFormats")}
            </styled.p>
          )}
          <Button onClick={handleOpenInput}>
            {t("onboarding.loadDocuments")}
          </Button>
        </HStack>
      </Footer>
      <HiddenInput ref={inputRef} onChange={handleInputChange} />
    </>
  );
}
