import { css } from "@/styled/css";
import { Stack, styled } from "@/styled/jsx";
import {
  CaretDown as NextIcon,
  CaretUp as PreviousIcon,
  XCircle,
} from "phosphor-react";

import { Button } from "@/components";

const counterClass = css({
  display: "flex",
  alignItems: "center",
  gap: "1",
});

interface Props {
  count: number;
  cursor: number;
  next: () => void;
  previous: () => void;
  clear: () => void;
}

export const Counter = ({ count, previous, next, cursor, clear }: Props) => {
  // Only return the counter if there is a match
  if (count === 0) return null;

  return (
    <div className={counterClass}>
      <styled.button cursor="pointer" onClick={clear}>
        <XCircle fill="#625C68" color="#625C68" size={24} />
      </styled.button>
      <styled.span
        textStyle="label.md.default"
        color="text.lighter"
        whiteSpace="nowrap"
      >
        {cursor} de {count}
      </styled.span>
      {/* <styled.span textStyle="label.md.default" color="text.lighter">
      </styled.span> */}
      <Stack direction="row" flexWrap="nowrap" gap="1">
        <Button onClick={previous} variant="none" disabled={cursor === 1}>
          <PreviousIcon size={24} />
        </Button>
        <Button onClick={next} variant="none" disabled={cursor === count}>
          <NextIcon size={24} />
        </Button>
      </Stack>
    </div>
  );
};
