import { TabName as FileName, Tab as FileStep, Stack } from "@/components";
import { useFiles } from "@/hooks";
import type { DocFile } from "@/types/file";
import { CaretButton, Carousel } from "./FileStepper.styles";
import Icons from "./Icons";
import { canMoveLeft as checkLeft, canMoveRight as checkRight } from "./utils";

interface Props {
  selected: number;
  nextFile: () => void;
  previousFile: () => void;
}
export default function FileStepper({
  selected,
  nextFile,
  previousFile,
}: Props) {
  const files = useFiles();

  const canMoveLeft = checkLeft(selected, files);
  const canMoveRight = checkRight(selected, files);
  const isLeftDisabled = selected === 0;
  const isRightDisabled = selected === files.length - 1; // -1 because we are using base 0 notation

  const getStatus = (current: number, file: DocFile) => {
    if (file.validated) {
      return "completed";
    }
    return selected === current ? "focus" : "default";
  };

  return (
    <Stack css={{ overflow: "scroll", p: "$s" }}>
      {/* <- */}
      <CaretButton
        variant="tertiary"
        disabled={isLeftDisabled || !canMoveLeft}
        onClick={previousFile}
      >
        <Icons.ArrowLeft />
      </CaretButton>

      {/* List of files */}
      <Carousel>
        {files.map((file, i) => (
          <FileStep key={file.data.name} status={getStatus(i, file)}>
            <FileName css={{ width: 200 }}>{file.data.name}</FileName>
            <Icons.Check status={getStatus(i, file)} />
          </FileStep>
        ))}
      </Carousel>

      {/* -> */}
      <CaretButton
        variant="tertiary"
        disabled={isRightDisabled || !canMoveRight}
        onClick={nextFile}
      >
        <Icons.ArrowRight />
      </CaretButton>
    </Stack>
  );
}
