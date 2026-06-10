import { ArrowsLeftRight, Stop, X } from "phosphor-react";
import { type ChangeEventHandler, type MouseEventHandler, useRef } from "react";

import HiddenInput from "@/components/hidden-input";
import Button from "@/components/ui/button";
import { useFileDispatch } from "@/hooks";
import type { PredictStatus } from "@/hooks/usePredict";
import { removeFile, replaceFile } from "@/reducers/file/actions";
import { css } from "@/styled/css";
import { Stack } from "@/styled/jsx";
import { useQueryClient } from "@tanstack/react-query";
import ProgressBar from "./ProgressBar";

function ActionButton({
  status,
  onClick,
}: { status: PredictStatus; onClick: MouseEventHandler }) {
  return (
    <Button onClick={onClick} className={css({ w: "36" })}>
      {status === "processing" ? (
        <>
          <Stop weight="bold" />
          Detener
        </>
      ) : (
        <>
          <ArrowsLeftRight weight="bold" />
          Reemplazar
        </>
      )}
    </Button>
  );
}

interface Props {
  fileName: string;
  status: PredictStatus;
  progress: number;
  onAbort?: () => void;
}
export default function FileProcessing({
  fileName,
  status,
  progress,
  onAbort,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const dispatch = useFileDispatch();
  const queryClient = useQueryClient();

  const handleOpenFinder = () => {
    inputRef.current?.click();
  };

  const handleAddedFile: ChangeEventHandler<HTMLInputElement> = (e) => {
    const rawFiles = e.target.files;

    if (rawFiles) {
      const fileList = Array.from(rawFiles);
      if (fileList.length > 0) {
        queryClient.removeQueries({
          queryKey: ["file-parser", fileName],
          exact: false,
        });
        queryClient.removeQueries({
          queryKey: ["disambiguate", fileName],
          exact: false,
        });
        queryClient.removeQueries({
          predicate: (query) => {
            const key = query.queryKey as unknown[];
            return key[0] === "predict" && key[2] === fileName;
          },
        });
        dispatch(replaceFile(fileName, fileList[0]));
      }
    }
  };

  const handleStop = () => {
    onAbort?.();
  };

  const remove = () => {
    onAbort?.();
    dispatch(removeFile(fileName));
  };

  return (
    <Stack align="center" gap="4" width="full" direction="row">
      <HiddenInput
        multiple={false}
        style={{ position: "absolute" }}
        ref={inputRef}
        onChange={handleAddedFile}
      />
      <ProgressBar
        status={status}
        fileName={fileName}
        progress={status === "stopped" ? 0 : Math.round(progress * 100)}
      />
      <ActionButton
        status={status}
        onClick={status === "processing" ? handleStop : handleOpenFinder}
      />
      <Button variant="none" onClick={remove}>
        <X />
      </Button>
    </Stack>
  );
}
