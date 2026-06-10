import {
  type ChangeEvent,
  type KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import AnonymizerLabelSelect from "@/components/anonymizer/anonymizer-label-select";
import Button from "@/components/ui/button";
import type { SelectOption } from "@/components/ui/select";
import { useExcludedTagsConfig } from "@/store/useLocal";
import { sva } from "@/styled/css";
import { Grid, HStack, styled } from "@/styled/jsx";
import { hstack } from "@/styled/patterns";
import { getActiveAnonymizerLabelOptions } from "@/utils/anonymizer/labels";
import { MagnifyingGlass } from "phosphor-react";
import { SEARCH_MIN_LENGTH } from "../annotations";
import { Counter } from "./Counter";

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
  labelValue?: string;
  onLabelManagerToggle: () => void;
  matchesCount: number;
  activeIndex: number | null;
  onNext: () => void;
  onPrevious: () => void;
  onFocusDocument: () => void;
}

export const SearchBar = ({
  isAnnotable = false,
  isLabelManagerOpen,
  onSearchChange,
  onLabelChange,
  labelValue,
  onLabelManagerToggle,
  matchesCount,
  activeIndex,
  onNext,
  onPrevious,
  onFocusDocument,
}: Props) => {
  const [search, setSearch] = useState("");
  const { tags } = useExcludedTagsConfig();

  const inputSearchRef = useRef<HTMLInputElement>(null);

  const classes = searchClasses();
  const labelOptions = getActiveAnonymizerLabelOptions(tags);

  useEffect(() => {
    const isEditableTarget = (target: EventTarget | null) => {
      if (!(target instanceof HTMLElement)) return false;
      if (target === inputSearchRef.current) return false;
      if (target.isContentEditable) return true;
      return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
    };

    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      const isSearchShortcut =
        (event.ctrlKey || event.metaKey) &&
        !event.altKey &&
        !event.shiftKey &&
        event.key.toLowerCase() === "b";

      if (!isSearchShortcut || isEditableTarget(event.target)) return;

      event.preventDefault();
      inputSearchRef.current?.focus();
      inputSearchRef.current?.select();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

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

  const handleInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    handleClear();
    onFocusDocument();
  };

  const searchFocus = () => inputSearchRef.current?.focus();

  const changeLabelSelectHandler = (e: SelectOption | undefined) => {
    onLabelChange?.(e);
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
          onKeyDown={handleInputKeyDown}
        />
        <Counter
          clear={handleClear}
          next={onNext}
          previous={onPrevious}
          count={matchesCount}
          cursor={activeIndex === null ? 0 : activeIndex + 1}
          isSearching={search.length >= SEARCH_MIN_LENGTH}
        />
      </div>
      {isAnnotable && (
        <HStack alignItems="center" gap="6">
          <hr className={classes.verticalHr} />
          <styled.p textStyle="label.md.strong" whiteSpace="pre-line">
            Aplicar&#10;etiquetas
          </styled.p>
          <div style={{ minWidth: 150 }}>
            <AnonymizerLabelSelect
              placeholder="Etiqueta"
              value={labelValue}
              options={labelOptions}
              onChange={changeLabelSelectHandler}
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
};
