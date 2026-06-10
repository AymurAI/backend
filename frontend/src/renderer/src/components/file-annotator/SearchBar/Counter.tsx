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
  isSearching: boolean;
}

export const Counter = ({
  count,
  previous,
  next,
  cursor,
  clear,
  isSearching,
}: Props) => {
  if (!isSearching) return null;

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
        {count === 0 ? "0 ocurrencias" : `${cursor} de ${count}`}
      </styled.span>
      <Stack direction="row" flexWrap="nowrap" gap="1">
        <Button
          onClick={previous}
          variant="none"
          disabled={count === 0 || cursor === 1}
        >
          <PreviousIcon size={24} />
        </Button>
        <Button
          onClick={next}
          variant="none"
          disabled={count === 0 || cursor === count}
        >
          <NextIcon size={24} />
        </Button>
      </Stack>
    </div>
  );
};
