import type React from "react";
import { useState } from "react";

import { sva } from "@/styled/css";
import { styled } from "@/styled/jsx";
import { hstack } from "@/styled/patterns";

import Input from "@/components/ui/input";
import Select, { type SelectOption } from "@/components/ui/select";
import { useAnnotation } from "@/context/Annotation";
import { type AllLabels, anonymizerLabels } from "@/types/aymurai";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import TaggerButton from "./tagger-button";

const IMG_SIZE = 24;

const tagger = sva({
  slots: ["container", "button", "divider", "tooltipContent"],
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
    tooltipContent: {
      bg: "action.hover",
      color: "white",
      px: "1",
      py: "0.5",
      rounded: "sm",
    },
  },
});

interface MarkTaggerProps {
  onClickOne: (label: AllLabels, suffix: number | null) => void;
  onClickAll: (label: AllLabels, suffix: number | null) => void;
  onDeleteOne?: () => void;
  onDeleteAll?: () => void;
}
export default function Tagger({ onClickAll, onClickOne, onDeleteOne, onDeleteAll }: MarkTaggerProps) {
  const { label: initialLabel, suffix: initialSuffix } = useAnnotation();

  const [label, setLabel] = useState<AllLabels | null>(initialLabel);
  const [suffix, setSuffix] = useState<number | null>(initialSuffix);
  const [isSelectOpen, setIsSelectOpen] = useState(false);

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
      <TooltipProvider delayDuration={0}>
        <Tooltip open={isSelectOpen ? false : undefined}>
          <TooltipTrigger asChild>
            <div>
              <Select
                placeholder="Etiqueta"
                size="sm"
                value={label ?? undefined}
                options={anonymizerLabels}
                onChange={handleLabelChange}
                onOpenChange={setIsSelectOpen}
              />
            </div>
          </TooltipTrigger>
          <TooltipContent showArrow={false} sideOffset={12}>
            <div className={classes.tooltipContent}>
              <styled.p textStyle="label.sm.default">Selecciona tipo de etiqueta</styled.p>
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <div className={classes.divider} />
      <TooltipProvider delayDuration={0}>
        <Tooltip>
          <TooltipTrigger asChild>
            <styled.div maxWidth="16">
              <Input
                placeholder="Sufijo"
                value={suffix ? suffix.toString() : undefined}
                size="sm"
                onChange={handleSuffixChange}
                type="number"
                min="1"
              />
            </styled.div>
          </TooltipTrigger>
          <TooltipContent showArrow={false} sideOffset={12}>
            <div className={classes.tooltipContent}>
              <styled.p textStyle="label.sm.default">Agrega sufijo si es necesario</styled.p>
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
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
      {onDeleteOne && (
        <>
          <div className={classes.divider} />
          <TaggerButton
            tooltip="Eliminar esta ocurrencia"
            onClick={onDeleteOne}
          >
            <img
              src={`${import.meta.env.BASE_URL}button-icons/delete-one.svg`}
              alt="Eliminar esta ocurrencia"
              width={IMG_SIZE}
              height={IMG_SIZE}
            />
          </TaggerButton>
        </>
      )}
      {onDeleteAll && (
        <>
          <div className={classes.divider} />
          <TaggerButton
            tooltip="Eliminar todas las ocurrencias"
            onClick={onDeleteAll}
          >
            <img
              src={`${import.meta.env.BASE_URL}button-icons/delete-all.svg`}
              alt="Eliminar todas las ocurrencias"
              width={IMG_SIZE}
              height={IMG_SIZE}
            />
          </TaggerButton>
        </>
      )}
    </div>
  );
}
