import { useFiles } from "@/hooks/useFiles";
import filesystem from "@/services/filesystem";
import { HStack } from "@/styled/jsx";
import { FeatureFlowEnum } from "@/types/features";
import type { DocFile } from "@/types/file";
import { submitValidations } from "@/utils/file";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import FileCheck from "../file-check";
import Footer from "../layout/footer";
import Button from "../ui/button";
import FinishMainContent from "./finish-main-content";

interface FinishDatasetProps {
  onRestart: () => void;
}
export default function FinishDataset({ onRestart }: FinishDatasetProps) {
  const { t } = useTranslation("dataset");
  const files = useFiles();

  const [errorNames, setErrorNames] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const didSubmit = useRef(false);

  const checkForErrors = (fileName: string) =>
    !!errorNames.find((name) => name === fileName);

  const submit = useCallback(
    async (file: DocFile) => {
      try {
        // POST the validated data to the dataset
        await submitValidations({
          isOnline: false,
          validations: file.validationObject,
        });
      } catch (error) {
        console.error("[dataset] Error saving validations", {
          fileName: file.data.name,
          error,
        });
        setErrorNames((names) => [...names, file.data.name]);
      }

      // Export the feedback JSON
      await filesystem.feedback.export(files);
    },
    [files],
  );

  // At first render, submit all the data
  useEffect(() => {
    if (didSubmit.current) return;
    didSubmit.current = true;

    const submitAll = async () => {
      for (const file of files) {
        await submit(file);
      }
    };

    submitAll().then(() => setIsLoading(false));

    // We strictly need to run this effect once
  }, [files, submit]);

  return (
    <>
      <FinishMainContent feature={FeatureFlowEnum.Dataset}>
        {files.map(({ data }) => (
          <FileCheck
            key={data.name}
            fileName={data.name}
            hasError={checkForErrors(data.name)}
            {...{ isLoading }}
          />
        ))}
      </FinishMainContent>
      <Footer withBuiltBy>
        <HStack alignItems="center" gap="4">
          <Button variant="secondary" onClick={onRestart} size="md">
            {t("finish.restart")}
          </Button>
          <Button size="md" onClick={filesystem.excel.open}>
            {t("finish.viewResult")}
          </Button>
        </HStack>
      </Footer>
    </>
  );
}
