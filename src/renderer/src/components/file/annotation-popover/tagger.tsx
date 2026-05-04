import type React from "react";
import { useState } from "react";

import { sva } from "@/styled/css";
import { styled } from "@/styled/jsx";
import { hstack } from "@/styled/patterns";

import Input from "@/components/ui/input";
import Select, { type SelectOption } from "@/components/ui/select";
import { useAnnotation } from "@/context/Annotation";
import { type AllLabels, anonymizerLabels } from "@/types/aymurai";

import TaggerButton from "./tagger-button";

const IMG_SIZE = 24;

const tagger = sva({
  slots: ["container", "button", "divider"],
  base: {
    container: {
      ...hstack.raw({ alignItems: "center", gap: "1" }),
      p: "1",
      bg: "action.alt-default",
      rounded: "lg",
    },
    button: {
      cursor: "pointer",
    },
    divider: {
      alignSelf: "stretch",
      width: "[1px]",
      bg: "[#5960B0]",

      my: "1",
    },
  },
});

interface MarkTaggerProps {
  onClickOne: (label: AllLabels, suffix: number | null) => void;
  onClickAll: (label: AllLabels, suffix: number | null) => void;
}
export default function Tagger({ onClickAll, onClickOne }: MarkTaggerProps) {
  const { label: initialLabel, suffix: initialSuffix } = useAnnotation();

  const [label, setLabel] = useState<AllLabels | null>(initialLabel);
  const [suffix, setSuffix] = useState<number | null>(initialSuffix);

  const handleClickOne = () => {
    if (!label) return;
    onClickOne(label, suffix);
  };
  const handleClickAll = () => {
    if (!label) return;
    onClickAll(label, suffix);
  };

  const handleLabelChange = (value: SelectOption) => {
    setLabel(value.id as AllLabels);
  };
  const handleSuffixChange: React.ChangeEventHandler<HTMLInputElement> = (
    e,
  ) => {
    const n = Number(e.target.value);
    if (Number.isNaN(n)) throw new Error("Tried to input a non-numeric value!");
    setSuffix(n);
  };

  const classes = tagger();
  return (
    <div className={classes.container}>
      <Select
        size="sm"
        value={label ?? undefined}
        options={anonymizerLabels}
        onChange={handleLabelChange}
      />
      <div className={classes.divider} />
      <styled.div maxWidth="16">
        <Input
          value={suffix ? suffix.toString() : undefined}
          size="sm"
          onChange={handleSuffixChange}
          type="number"
          min="1"
        />
      </styled.div>
      <div className={classes.divider} />
      <TaggerButton
        tooltip="Afectar una ocurrencia"
        onClick={handleClickOne}
        disabled={!label}
      >
        <img
          src={`${import.meta.env.BASE_URL}button-icons/add-one.svg`}
          alt="Afectar una ocurrencia"
          width={IMG_SIZE}
          height={IMG_SIZE}
        />
      </TaggerButton>
      <div className={classes.divider} />
      <TaggerButton
        tooltip="Afectar todas las ocurrencias"
        onClick={handleClickAll}
        disabled={!label}
      >
        <img
          src={`${import.meta.env.BASE_URL}button-icons/add-all.svg`}
          alt="Afectar todas las ocurrencias"
          width={IMG_SIZE}
          height={IMG_SIZE}
        />
      </TaggerButton>
    </div>
  );
}
