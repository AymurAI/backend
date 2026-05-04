import { Button, FilePreview } from "@/components";
import HiddenInput from "@/components/hidden-input";
import Stepper from "@/components/home/stepper";
import Footer from "@/components/layout/footer";
import Header from "@/components/layout/header";
import MainContent from "@/components/layout/main-content";
import BackButton from "@/components/ui/back-button";
import Card from "@/components/ui/card";
import RequireFile from "@/features/RequireFile";
import { useFileDispatch, useFiles } from "@/hooks";
import { useFileParse } from "@/hooks/useFileParse";
import { SectionTitle } from "@/layout/section-title";
import { addFiles, filterUnselected } from "@/reducers/file/actions";
import { css } from "@/styled/css";
import { Grid, HStack, Stack, styled } from "@/styled/jsx";
import { FeatureFlowEnum, featureNamespace } from "@/types/features";
import {
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

export const Route = createFileRoute("/app/$feature/preview")({
  component: RouteComponent,
});

function RouteComponent() {
  const { feature } = useParams({
    from: "/app/$feature/preview",
  });
  const navigate = useNavigate();
  const { t } = useTranslation(featureNamespace[feature]);

  const inputRef = useRef<HTMLInputElement>(null);

  const files = useFiles();
  const dispatch = useFileDispatch();
  const parseStatuses = useFileParse(files);

  const isProcessing = files.some((file) => !file.paragraphs);

  const handleAddFiles: React.ChangeEventHandler<HTMLInputElement> = async (
    e,
  ) => {
    const rawFiles = e.target.files;
    if (rawFiles) {
      dispatch(addFiles([...rawFiles]));
      await navigate({
        to: "/app/$feature/preview",
        params: { feature },
      });
    }
  };
  const handleOpenInput = () => {
    inputRef.current?.click();
  };

  const handleConfirmFiles = () => {
    dispatch(filterUnselected());
    navigate({
      to: "/app/$feature/process",
      params: { feature },
    });
  };

  return (
    <RequireFile>
      <Header
        title={t("title")}
        center={<Stepper currentStep={1} />}
        feature={feature}
      />
      <MainContent>
        <Stack gap="8">
          <HStack alignItems="center" gap="6">
            <BackButton to="/app/$feature/onboarding" params={{ feature }} />
            <SectionTitle>{t("preview.sectionTitle")}</SectionTitle>
          </HStack>
          <Card>
            <Stack gap="8">
              <styled.h2 textStyle="subtitle.md.default">
                {t("preview.filesLabel")}
              </styled.h2>
              <Grid columns={5}>
                {files.map((file) => (
                  <FilePreview
                    key={file.data.name}
                    file={file}
                    status={parseStatuses[file.data.name]?.status ?? "processing"}
                  />
                ))}
              </Grid>
            </Stack>
          </Card>
        </Stack>
      </MainContent>
      <Footer withBuiltBy>
        <HStack gap="4">
          {feature === FeatureFlowEnum.Dataset && (
            <>
              <styled.p textStyle="paragraph.sm.default" whiteSpace="nowrap">
                {t("preview.validFormats")}
              </styled.p>
              <Button
                variant="secondary"
                onClick={handleOpenInput}
                className={css({ whiteSpace: "nowrap" })}
              >
                {t("preview.loadMore")}
              </Button>
            </>
          )}
          <Button onClick={handleConfirmFiles} disabled={isProcessing}>
            {t("preview.continue")}
          </Button>
        </HStack>
      </Footer>
      <HiddenInput ref={inputRef} onChange={handleAddFiles} />
    </RequireFile>
  );
}
