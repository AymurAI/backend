import { CaretDown as NextIcon, CaretUp as PreviousIcon } from "phosphor-react";
import * as S from "./SearchBar.styles";

import { Button, Label, Stack } from "@/components";

interface Props {
  matchesCount: number;
  count: number;
  next: () => void;
  previous: () => void;
}

export const Counter = ({ matchesCount, previous, next, count }: Props) => {
  // Only return the counter if there is a match
  if (matchesCount === 0) return null;

  return (
    <S.Counter>
      <Label css={{ color: "$textDefault" }}>{count}</Label>
      <Label>de {matchesCount}</Label>
      <Stack direction="row" wrap="nowrap" spacing="xxs">
        <Button onClick={previous} variant="none" disabled={count === 1}>
          <PreviousIcon size={24} />
        </Button>
        <Button onClick={next} variant="none" disabled={count === matchesCount}>
          <NextIcon size={24} />
        </Button>
      </Stack>
    </S.Counter>
  );
};
