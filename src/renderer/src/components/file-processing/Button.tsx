import { ArrowsLeftRight as Restart, Stop } from "phosphor-react";

import { Button as BaseButton } from "@/components";
import type { PredictStatus } from "@/hooks/usePredict";

interface Props {
  status: PredictStatus;
  onStop?: () => void;
  onReplace?: () => void;
}
export default function Button({ status, onStop, onReplace }: Props) {
  const style = {
    minWidth: 210,
    gap: "$xs",
  };

  return status === "processing" ? (
    <BaseButton onClick={onStop} variant="secondary" css={style} size="s">
      <Stop weight="bold" />
      Detener
    </BaseButton>
  ) : (
    <BaseButton onClick={onReplace} variant="secondary" css={style} size="s">
      <Restart weight="bold" />
      Reemplazar
    </BaseButton>
  );
}
