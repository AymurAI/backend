import { useFiles } from "@/hooks";
import { aymuraiService } from "@/services/aymurai";
import { useExcludedTagsConfig } from "@/store/useLocal";
import { HStack } from "@/styled/jsx";
import { FeatureFlowEnum } from "@/types/features";
import { useMutation, useQuery } from "@tanstack/react-query";
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

  const {
    data: odtFile,
    isLoading,
    isError,
  } = useQuery(aymuraiService.anonymize(file, tags, words));

  const { mutate: convertToPdf, isPending: isPdfPending } = useMutation(
    aymuraiService.odtToPdf(),
  );

  const downloadDocument = () => {
    if (!odtFile) {
      console.error("Tried to download a file that is not ready.");
      return;
    }
    triggerDownload(odtFile, changeExtension(file.data.name));
  };

  const downloadPdf = () => {
    if (!odtFile) {
      console.error("Tried to download a file that is not ready.");
      return;
    }

    convertToPdf(odtFile, {
      onSuccess: (pdfBlob) => {
        triggerDownload(pdfBlob, changeExtension(file.data.name, "pdf"));
      },
    });
  };

  return (
    <>
      <FinishMainContent feature={FeatureFlowEnum.Anonymizer}>
        <FileCheck
          fileName={file.data.name}
          hasError={isError}
          isLoading={isLoading}
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
            isLoading={isLoading}
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
