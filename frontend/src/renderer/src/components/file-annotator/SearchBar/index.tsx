import { type ChangeEvent, useRef, useState } from "react";

import Button from "@/components/ui/button";
import Input from "@/components/ui/input";
import Select, { type SelectOption } from "@/components/ui/select";
import { sva } from "@/styled/css";
import { Grid, HStack, styled } from "@/styled/jsx";
import { hstack } from "@/styled/patterns";
import { anonymizerLabels } from "@/types/aymurai";
import { MagnifyingGlass } from "phosphor-react";
import { Counter } from "./Counter";
import { useScroll } from "./useScroll";

const searchClasses = sva({
  slots: ["searchBar", "input", "verticalHr"],
  base: {
    searchBar: {
      ...hstack.raw({ alignItems: "center", gap: "2" }),
      height: "12",
      p: "3",
      rounded: "3xl",
      // minWidth: "[450px]",
      width: "full",
      border: "primary",
    },
    input: {
      outline: "none",
      width: "full",
    },
    verticalHr: {
      width: "[1px]",
      alignSelf: "stretch",
      borderWidth: "0",
      backgroundColor: "[#BCBAB8]",
      height: "12",
    },
  },
});

interface Props {
  isAnnotable?: boolean;
  isLabelManagerOpen: boolean;
  onSearchChange?: (value: string) => void;
  onLabelChange?: (object: SelectOption | undefined) => void;
  onLabelSufixChange?: (value: number | null) => void;
  onLabelManagerToggle: () => void;
}

export const SearchBar = ({
  isAnnotable = false,
  isLabelManagerOpen,
  onSearchChange,
  onLabelChange,
  onLabelSufixChange,
  onLabelManagerToggle,
}: Props) => {
  const [search, setSearch] = useState("");
  const [labelSufix, setLabelSufix] = useState("");

  const inputSearchRef = useRef<HTMLInputElement>(null);

  const { next, previous, count, matchesCount } = useScroll(search);

  const classes = searchClasses();

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

  const handleClear = () => {
    setSearch("");
    onSearchChange?.("");
  };

  const searchFocus = () => inputSearchRef.current?.focus();

  // biome-ignore lint/suspicious/noExplicitAny: we should add a type in the future
  const changeLabelSelectHandler = (e: any | undefined) => {
    onLabelChange?.(e);
    onLabelSufixChange?.(null);
    setLabelSufix("");
  };

  const changeLabelSufixHandler = (e: ChangeEvent<HTMLInputElement>) => {
    setLabelSufix(e.target.value);
    onLabelSufixChange?.(Number(e.target.value));
  };

  return (
    <Grid
      gridTemplateColumns="minmax(0, 1fr) auto"
      px="8"
      py="6"
      gap="6"
      alignItems="center"
    >
      <div className={classes.searchBar} onClick={searchFocus}>
        <styled.span flexShrink="0" lineHeight="[0]">
          <MagnifyingGlass size={24} />
        </styled.span>
        <input
          type="text"
          placeholder="Buscar"
          value={search}
          className={classes.input}
          onChange={changeSearchHandler}
          onClick={clickSearchHandler}
        />
        <Counter
          clear={handleClear}
          next={next}
          previous={previous}
          count={matchesCount}
          cursor={count}
        />
      </div>
      {isAnnotable && (
        <HStack alignItems="center" gap="6">
          <hr className={classes.verticalHr} />
          <styled.p textStyle="label.md.strong" whiteSpace="pre-line">
            Aplicar&#10;etiquetas
          </styled.p>
          <div style={{ minWidth: 150 }}>
            <Select
              placeholder="Etiqueta"
              options={anonymizerLabels}
              onChange={changeLabelSelectHandler}
            />
          </div>
          <div style={{ width: 100 }}>
            <Input
              placeholder="Sufijo"
              value={labelSufix}
              onChange={changeLabelSufixHandler}
              type="number"
              min={1}
            />
          </div>
          {!isLabelManagerOpen && (
            <>
              <hr className={classes.verticalHr} />
              <Button
                variant="secondary"
                onClick={onLabelManagerToggle}
                style={{ whiteSpace: "nowrap" }}
              >
                Gestor de etiquetas
              </Button>
            </>
          )}
        </HStack>
      )}
    </Grid>
  );
  // return (
  //   <Grid
  //     columns={isAnnotable ? 2 : 1}
  //     spacing="m"
  //     justify="stretch"
  //     align="stretch"
  //   >
  //     <S.WrapperSearch onClick={searchFocus}>
  //       <MagnifyingGlass size={24} />
  //       <S.InputContainer>
  //         <S.Input
  //           ref={inputSearchRef}
  //           placeholder="Buscar"
  //           onChange={changeSearchHandler}
  //           onClick={clickSearchHandler}
  //         />
  //       </S.InputContainer>

  //       <Counter {...{ next, previous, matchesCount, count }} />
  //     </S.WrapperSearch>

  //     {isAnnotable && (
  //       <S.ContainerLabel>
  //         <S.WrapperLabel>
  //           <Select
  //             placeholder="Seleccione una opción"
  //             options={anonymizerLabels}
  //             onChange={changeLabelSelectHandler}
  //           />
  //         </S.WrapperLabel>
  //         <S.WrapperSufixLabel>
  //           <S.InputContainer>
  //             <S.Input
  //               ref={inputLabelSufixRef}
  //               placeholder="Sufijo"
  //               onChange={changeLabelSufixHandler}
  //               type="number"
  //               min="1"
  //             />
  //           </S.InputContainer>
  //         </S.WrapperSufixLabel>
  //       </S.ContainerLabel>
  //     )}
  //   </Grid>
  // );
};
