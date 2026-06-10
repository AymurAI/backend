import { Label, Stack } from "@/components";
import type { PredictStatus } from "@/hooks/usePredict";
import { CheckCircle } from "phosphor-react";
import { Bar, BarContainer } from "./FileProcessing.styles";
import { ProgressLabel } from "./ProgressLabel";

interface Props {
  fileName: string;
  progress: number;
  status: PredictStatus;
}
export default function ProgressBar({ fileName, progress, status }: Props) {
  const getProgressText = () => {
    const text = {
      processing: `${progress}%`,
      completed: (
        <>
          <CheckCircle /> Carga finalizada 100%
        </>
      ),
      error: "Error de carga de archivo. Volvelo a intentar",
      stopped: "Detuviste el procesamiento de este archivo",
    };

    return text[status];
  };

  return (
    <Stack direction="column" align="stretch" spacing="s" css={{ flex: 1 }}>
      {/* Texts */}
      <Stack justify="space-between">
        <Label status={status === "error" ? "error" : "default"}>
          {fileName}
        </Label>
        <ProgressLabel progress={status} css={{}}>
          {getProgressText()}
        </ProgressLabel>
      </Stack>

      <BarContainer>
        <Bar isCompleted={progress === 100} css={{ width: `${progress}%` }} />
      </BarContainer>
    </Stack>
  );
}
