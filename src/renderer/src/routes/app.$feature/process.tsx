import {
  Button,
  Card,
  FileProcessing,
  SectionTitle,
  Stack,
  Subtitle,
  Text,
  Toast,
} from "@/components";
import { useFileDispatch, useFiles } from "@/hooks";
import useNotify from "@/hooks/useNotify";
import type { PredictStatus } from "@/hooks/usePredict";
import { Footer, Section } from "@/layout/main";
import {
  filterUnprocessed,
  removeAllPredictions,
} from "@/reducers/file/actions";
import { Feature } from "@/types/features";
import { canContinue } from "@/utils/process/canContinue";
import {
  type ProcessState,
  initProcessState,
} from "@/utils/process/initProcessState";
import {
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { Bell } from "phosphor-react";
import { useState } from "react";

export const Route = createFileRoute("/app/$feature/process")({
  component: RouteComponent,
});

/**
 * Updates the status of a file in the state
 * @param name Name of the file to be updated
 * @param newValue New `PredictStatus` value to be updated
 * @param state `ProcessState[]` state in `/process` page
 * @returns A new array with the status of the given file changed
 */
function replace(
  name: string,
  value: Partial<ProcessState>,
  state: ProcessState[],
) {
  return state.map((process) => {
    if (process.name === name) return { ...process, ...value };
    return process;
  });
}

interface GenericProcessProps {
  title: string;
  finishText: string;
  supportMultipleFiles: boolean;
}
function GenericProcess({
  title,
  supportMultipleFiles,
  finishText,
}: GenericProcessProps) {
  const { feature } = useParams({ from: "/app/$feature/process" });
  const navigate = useNavigate();
  const dispatch = useFileDispatch();
  const files = useFiles();
  const [process, setProcess] = useState(initProcessState(files));
  const { isToastVisible, hideToast } = useNotify(process);

  const handleStatusChange = (name: string) => (newValue: PredictStatus) => {
    // Replace the newValue
    setProcess((cur) => replace(name, { status: newValue }, cur));
  };
  const handleReplaceFile = (name: string) => (newName: string) => {
    setProcess((cur) =>
      replace(name, { name: newName, status: "processing" }, cur),
    );
  };

  const handlePrevious = () => {
    navigate({
      to: "/app/$feature/preview",
      params: { feature },
    });
    dispatch(removeAllPredictions());
  };

  const handleNext = () => {
    dispatch(filterUnprocessed());
    navigate({
      to: "/app/$feature/validation",
      params: { feature },
    });
  };

  return (
    <>
      <Section>
        <Toast isVisible={isToastVisible} onClose={hideToast} icon={<Bell />}>
          {finishText}
        </Toast>
        <SectionTitle onClick={handlePrevious}>{title}</SectionTitle>
        <Card css={{ alignItems: "stretch" }}>
          <Stack spacing="l" direction="column">
            <Stack direction="column" spacing="xs">
              {supportMultipleFiles ? (
                <Text>AymurAI está extrayendo los datos de los archivos</Text>
              ) : (
                <Text>AymurAI está extrayendo los datos del archivo</Text>
              )}
              <Subtitle size="s">
                Este proceso puede tardar algunos minutos.
              </Subtitle>
            </Stack>
            {files.map((f) => (
              <FileProcessing
                key={f.data.name}
                file={f}
                onStatusChange={handleStatusChange(f.data.name)}
                onFileReplace={handleReplaceFile(f.data.name)}
              />
            ))}
          </Stack>
        </Card>
      </Section>
      <Footer>
        <Button size="l" disabled={!canContinue(process)} onClick={handleNext}>
          Siguiente
        </Button>
      </Footer>
    </>
  );
}

function RouteComponent() {
  const { feature } = useParams({
    from: "/app/$feature/process",
  });

  if (feature === Feature.Dataset)
    return (
      <GenericProcess
        title="2. Procesamiento de los archivos"
        finishText="Se finalizó el análisis de tus documentos."
        supportMultipleFiles={true}
      />
    );

  return (
    <GenericProcess
      title="2. Procesamiento del archivo"
      supportMultipleFiles={false}
      finishText="Se finalizó el análisis del documento."
    />
  );
}
