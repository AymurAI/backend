import { Button, FileProcessing } from "@/components";
import Stepper from "@/components/home/stepper";
import Footer from "@/components/layout/footer";
import Header from "@/components/layout/header";
import MainContent from "@/components/layout/main-content";
import BackButton from "@/components/ui/back-button";
import Callout from "@/components/ui/callout";
import Card from "@/components/ui/card";
import RequireFile from "@/features/RequireFile";
import { useFileDispatch, useFiles } from "@/hooks";
import { useDisambiguate } from "@/hooks/useDisambiguate";
import { useFileParse } from "@/hooks/useFileParse";
import { type PredictStatus, usePredict } from "@/hooks/usePredict";
import { SectionTitle } from "@/layout/section-title";
import { filterUnprocessed } from "@/reducers/file/actions";
import { css } from "@/styled/css";
import { HStack, Stack, styled } from "@/styled/jsx";
import type { Workflows } from "@/types/aymurai";
import { FeatureFlowEnum, featureNamespace } from "@/types/features";
import type { DocFile } from "@/types/file";
import taskbar from "@/services/taskbar";
import { useQueryClient } from "@tanstack/react-query";
import {
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

export const Route = createFileRoute("/app/$feature/process")({
  component: RouteComponent,
});

function RouteComponent() {
  const queryClient = useQueryClient();
  const { feature } = useParams({
    from: "/app/$feature/process",
  });
  const { t } = useTranslation(featureNamespace[feature]);

  const dispatch = useFileDispatch();
  const navigate = useNavigate();
  const files = useFiles();

  const [isDismissed, setIsDismissed] = useState(false);
  const hasNotified = useRef(false);

  const workflow: Workflows =
    feature === FeatureFlowEnum.Anonymizer ? "anonymizer" : "datapublic";
  const parseStatuses = useFileParse(files);
  const fileStatuses = usePredict(files, workflow);
  const disambiguateStatuses = useDisambiguate(
    files,
    fileStatuses,
    workflow === "anonymizer",
  );

  const handleNext = () => {
    dispatch(filterUnprocessed());
    navigate({
      to: "/app/$feature/validation",
      params: { feature },
    });
  };

  const isProcessing = files.some(
    (f) =>
      parseStatuses[f.data.name]?.status === "processing" ||
      fileStatuses[f.data.name]?.status === "processing" ||
      disambiguateStatuses[f.data.name]?.status === "processing",
  );

  useEffect(() => {
    if (files.length > 0 && !isProcessing && !hasNotified.current) {
      hasNotified.current = true;
      taskbar.notify();
    }
  }, [isProcessing, files.length]);

  // Weighted progress: 10% parse / 70% predict / 20% disambiguate (anonymizer)
  // or 10% parse / 90% predict (datapublic).
  const getProgress = (fileName: string): number => {
    const parseDone = parseStatuses[fileName]?.status === "completed" ? 1 : 0;
    const predictProgress = fileStatuses[fileName]?.progress ?? 0;

    if (workflow !== "anonymizer") {
      return parseDone * 0.1 + predictProgress * 0.9;
    }
    const disambiguateDone =
      disambiguateStatuses[fileName]?.status === "completed" ? 1 : 0;
    return parseDone * 0.1 + predictProgress * 0.7 + disambiguateDone * 0.2;
  };

  // Status accounts for all three stages so "completed" only shows at 100%.
  const getCombinedStatus = (fileName: string): PredictStatus => {
    const parseStatus = parseStatuses[fileName]?.status ?? "processing";
    if (parseStatus !== "completed") return parseStatus;

    const predictStatus = fileStatuses[fileName]?.status ?? "processing";
    if (workflow !== "anonymizer" || predictStatus !== "completed")
      return predictStatus;

    return disambiguateStatuses[fileName]?.status ?? "processing";
  };

  const handleAbort = (file: DocFile) => () => {
    queryClient.removeQueries({
      queryKey: ["file-parser", file.data.name],
      exact: false,
    });
    queryClient.removeQueries({
      queryKey: ["predict", feature, file.data.name],
      exact: false,
    });
    fileStatuses[file.data.name]?.abort?.();
    parseStatuses[file.data.name]?.abort?.();
  };

  return (
    <RequireFile>
      <Header
        title={t("title")}
        feature={feature}
        center={<Stepper currentStep={2} />}
      />
      <MainContent>
        <Stack gap="10">
          <HStack alignItems="center" gap="6">
            <BackButton to="/app/$feature/preview" params={{ feature }} />
            <SectionTitle>{t("process.sectionTitle")}</SectionTitle>
          </HStack>
          <Card className={css({ alignItems: "stretch" })}>
            <Stack gap="6" direction="column">
              <Stack direction="column" gap="1">
                <styled.h2 textStyle="subtitle.md.default">
                  {t("process.processingTitle")}
                </styled.h2>
                <styled.p textStyle="subtitle.sm.default" color="text.lighter">
                  {t("process.processingSubtitle")}
                </styled.p>
              </Stack>
              {!isProcessing && !isDismissed && (
                <Callout
                  message={t("process.finishText")}
                  variant="info"
                  noBorder
                  onDismiss={() => setIsDismissed(true)}
                />
              )}
              {files.map((f) => (
                <FileProcessing
                  key={f.data.name}
                  fileName={f.data.name}
                  status={getCombinedStatus(f.data.name)}
                  progress={getProgress(f.data.name)}
                  onAbort={handleAbort(f)}
                />
              ))}
            </Stack>
          </Card>
        </Stack>
      </MainContent>
      <Footer withBuiltBy>
        <Button onClick={handleNext} disabled={isProcessing}>
          Siguiente
        </Button>
      </Footer>
    </RequireFile>
  );
}
