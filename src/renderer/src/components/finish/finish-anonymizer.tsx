import { showToast } from "@/features/showToast";
import { useFiles } from "@/hooks";
import { aymuraiService } from "@/services/aymurai";
import { useExcludedTagsConfig } from "@/store/useLocal";
import { HStack } from "@/styled/jsx";
import { FeatureFlowEnum } from "@/types/features";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import FileCheck from "../file-check";
import Footer from "../layout/footer";
import Button from "../ui/button";
import FinishMainContent from "./finish-main-content";

interface FinishAnonymizerProps {
  onRestart: () => void;
}

export default function FinishAnonymizer({ onRestart }: FinishAnonymizerProps) {
  const { t } = useTranslation("anonymizer");
  const file = useFiles().at(0);
  const { tags, words } = useExcludedTagsConfig();

  if (!file) throw new Error("Reached /finish but there's no file to read");

  const isPdfInput = getExtension(file.data.name) === "pdf";

  const {
    data: anonymizedFile,
    isLoading,
    isError,
    error,
  } = useQuery(aymuraiService.anonymize(file, tags, words));

  const { mutate: convertToPdf, isPending: isPdfPending } = useMutation(
    aymuraiService.odtToPdf(),
  );

  const { mutate: convertToOdt, isPending: isOdtPending } = useMutation(
    aymuraiService.pdfToOdt(),
  );

  const exportErrorMessage =
    error instanceof Error ? error.message : t("finish.downloadError");

  useEffect(() => {
    if (!isError) return;
    console.error("Anonymizer export failed:", error);
    showToast(exportErrorMessage, "error");
  }, [error, exportErrorMessage, isError]);

  const onConversionError = (error: Error) => {
    console.error("Conversion failed:", error);
    showToast(t("finish.downloadError"), "error");
  };

  const downloadDocument = () => {
    if (!anonymizedFile) {
      console.error("Tried to download a file that is not ready.");
      return;
    }

    if (isPdfInput) {
      convertToOdt(anonymizedFile, {
        onSuccess: (odtBlob) => {
          triggerDownload(odtBlob, changeExtension(file.data.name));
        },
        onError: onConversionError,
      });
    } else {
      triggerDownload(anonymizedFile, changeExtension(file.data.name));
    }
  };

  const downloadPdf = () => {
    if (!anonymizedFile) {
      console.error("Tried to download a file that is not ready.");
      return;
    }

    if (isPdfInput) {
      triggerDownload(anonymizedFile, changeExtension(file.data.name, "pdf"));
    } else {
      convertToPdf(anonymizedFile, {
        onSuccess: (pdfBlob) => {
          triggerDownload(pdfBlob, changeExtension(file.data.name, "pdf"));
        },
        onError: onConversionError,
      });
    }
  };

  return (
    <>
      <FinishMainContent feature={FeatureFlowEnum.Anonymizer}>
        <FileCheck
          fileName={file.data.name}
          hasError={isError}
          isLoading={isLoading}
          errorMessage={exportErrorMessage}
        />
      </FinishMainContent>
      <Footer withBuiltBy>
        <HStack alignItems="center" gap="4">
          <Button variant="secondary" onClick={onRestart}>
            {t("finish.restart")}
          </Button>
          <Button
            onClick={downloadDocument}
            disabled={isError}
            isLoading={isLoading || isOdtPending}
          >
            {t("finish.viewResult")}
          </Button>
          <Button
            onClick={downloadPdf}
            disabled={isError}
            isLoading={isLoading || isPdfPending}
          >
            {t("finish.viewResultPDF")}
          </Button>
        </HStack>
      </Footer>
    </>
  );
}

function getExtension(name: string) {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

function triggerDownload(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

function changeExtension(name: string, ext = "odt") {
  const parts = name.split(".");
  parts.pop();
  return `${parts.join(".")}_anonimizado.${ext}`;
}
