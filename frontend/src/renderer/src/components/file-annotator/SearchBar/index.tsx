import { type ChangeEvent, useRef, useState } from "react";

import { Grid } from "@/components";
import Select, { type SelectOption } from "@/components/select";
import { anonymizerLabels } from "@/types/aymurai";

import { MagnifyingGlass } from "phosphor-react";
import { Counter } from "./Counter";
import * as S from "./SearchBar.styles";
import { useScroll } from "./useScroll";

interface Props {
  isAnnotable?: boolean;
  onSearchChange?: (value: string) => void;
  onLabelChange?: (object: SelectOption | undefined) => void;
  onLabelSufixChange?: (value: number | null) => void;
}

export const SearchBar = ({
  isAnnotable = false,
  onSearchChange,
  onLabelChange,
  onLabelSufixChange,
}: Props) => {
  const [search, setSearch] = useState("");

  const inputSearchRef = useRef<HTMLInputElement>(null);
  const inputLabelSufixRef = useRef<HTMLInputElement>(null);

  const { next, previous, count, matchesCount } = useScroll(search);

  const changeSearchHandler = (e: ChangeEvent<HTMLInputElement>) => {
    const text = e.target.value;
    setSearch(text);
    onSearchChange?.(e.target.value);
  };

  const clickSearchHandler = () => {
    if (inputSearchRef.current) {
      inputSearchRef.current.select();
    }
  };

  const searchFocus = () => inputSearchRef.current?.focus();

  // biome-ignore lint/suspicious/noExplicitAny: we should add a type in the future
  const changeLabelSelectHandler = (e: any | undefined) => {
    onLabelChange?.(e);
    onLabelSufixChange?.(null);
    if (inputLabelSufixRef.current) {
      inputLabelSufixRef.current.value = "";
    }
  };

  const changeLabelSufixHandler = (e: ChangeEvent<HTMLInputElement>) => {
    onLabelSufixChange?.(Number(e.target.value));
  };

  return (
    <Grid
      columns={isAnnotable ? 2 : 1}
      spacing="m"
      justify="stretch"
      align="stretch"
    >
      <S.WrapperSearch onClick={searchFocus}>
        <MagnifyingGlass size={24} />
        <S.InputContainer>
          <S.Input
            ref={inputSearchRef}
            placeholder="Buscar"
            onChange={changeSearchHandler}
            onClick={clickSearchHandler}
          />
        </S.InputContainer>

        <Counter {...{ next, previous, matchesCount, count }} />
      </S.WrapperSearch>

      {isAnnotable && (
        <S.ContainerLabel>
          <S.WrapperLabel>
            <Select
              placeholder="Seleccione una opción"
              options={anonymizerLabels}
              onChange={changeLabelSelectHandler}
            />
          </S.WrapperLabel>
          <S.WrapperSufixLabel>
            <S.InputContainer>
              <S.Input
                ref={inputLabelSufixRef}
                placeholder="Sufijo"
                onChange={changeLabelSufixHandler}
                type="number"
                min="1"
              />
            </S.InputContainer>
          </S.WrapperSufixLabel>
        </S.ContainerLabel>
      )}
    </Grid>
  );
};
