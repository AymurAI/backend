import { HStack, Stack, styled } from "@/styled/jsx";
import type { AnonymizerLabels } from "@/types/aymurai";
import { useState } from "react";

import Button from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import Input from "@/components/ui/input";
import BaseSwitch from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  ANONYMIZER_CATEGORY_NAMES,
  getAnonymizerLabelsForCategory,
} from "@/constants/anonymizer-categories";
import { EXCLUDED_TAGS } from "@/constants/excluded-tags";
import {
  useExcludedTagsConfig,
  useExcludedTagsConfigActions,
} from "@/store/useLocal";
import { css } from "@/styled/css";
import { Trash } from "phosphor-react";
import { Label } from "./label";
import LabelManagerSection from "./section";

const iconButton = css({
  cursor: "pointer",
  color: "text.lighter",
  bg: "transparent",
  border: "[1px solid #BCBAB8]",
  rounded: "sm",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  p: "1.5",
  flexShrink: "0",
  "&:hover": {
    color: "white",
    bg: "action.hover",
    borderColor: "action.hover",
  },
});

const tooltipContent = css({
  bg: "action.hover",
  color: "white",
  px: "1.5",
  py: "0.5",
  rounded: "sm",
  fontSize: "[12px]",
  boxShadow: "[none]",
});

interface ToggleProps {
  name: string;
  value: boolean;
  onToggle: (value: boolean) => void;
}
function Switch({ name, value, onToggle }: ToggleProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <styled.div px="4" py="3" bg="bg.secondary" rounded="xs">
          <HStack justify="space-between">
            <styled.span textStyle="label.md.default">{name}</styled.span>
            <BaseSwitch checked={value} onCheckedChange={onToggle} />
          </HStack>
        </styled.div>
      </TooltipTrigger>
      <TooltipContent showArrow={false} className={tooltipContent}>
        Incluir o excluir esta categoría de la anonimización
      </TooltipContent>
    </Tooltip>
  );
}

interface LabelConfigTabProps {
  expandedSections: Record<string, boolean>;
  onSectionOpenChange: (section: string, open: boolean) => void;
}

const EXCLUDED_TERMS_SECTION = "Términos excluidos";

export default function LabelConfigTab({
  expandedSections,
  onSectionOpenChange,
}: LabelConfigTabProps) {
  const { tags: storedTags, words: storedWords } = useExcludedTagsConfig();
  const { setTags, setWords } = useExcludedTagsConfigActions();

  const [toggles, setToggles] = useState<Record<string, boolean>>(
    storedTags ?? EXCLUDED_TAGS,
  );
  const [excludedWords, setExcludedWords] = useState<string[]>(storedWords);
  const [inputValue, setInputValue] = useState("");
  const [clearDialogOpen, setClearDialogOpen] = useState(false);

  function handleToggle(id: string, value: boolean) {
    const next = { ...toggles, [id]: value };
    setToggles(next);
    setTags(next as Record<AnonymizerLabels, boolean>);
  }

  function handleAddWord() {
    const trimmed = inputValue.trim();
    if (!trimmed || excludedWords.includes(trimmed)) return;
    const next = [...excludedWords, trimmed];
    setExcludedWords(next);
    setWords(next);
    setInputValue("");
  }

  function handleRemoveWord(word: string) {
    const next = excludedWords.filter((w) => w !== word);
    setExcludedWords(next);
    setWords(next);
  }

  function handleClearAllWords() {
    setExcludedWords([]);
    setWords([]);
  }

  return (
    <TooltipProvider>
      <Stack gap="6" align="stretch">
        {ANONYMIZER_CATEGORY_NAMES.map((category, index) => (
          <Stack key={category} gap="4">
            {index > 0 && <styled.hr borderColor="[#BCBAB8]" />}
            <LabelManagerSection
              title={category}
              open={expandedSections[category] ?? true}
              onOpenChange={(open) => onSectionOpenChange(category, open)}
            >
              <Stack>
                {getAnonymizerLabelsForCategory(category).map((label) => (
                  <Switch
                    key={label.id}
                    name={label.text}
                    value={toggles[label.id]}
                    onToggle={(value) => handleToggle(label.id, value)}
                  />
                ))}
              </Stack>
            </LabelManagerSection>
          </Stack>
        ))}
        <styled.hr borderColor="[#BCBAB8]" />
        <LabelManagerSection
          title={EXCLUDED_TERMS_SECTION}
          open={expandedSections[EXCLUDED_TERMS_SECTION] ?? true}
          onOpenChange={(open) =>
            onSectionOpenChange(EXCLUDED_TERMS_SECTION, open)
          }
          headerAction={
            excludedWords.length > 0 ? (
              <button
                type="button"
                className={iconButton}
                onClick={() => setClearDialogOpen(true)}
                aria-label="Borrar todos los términos excluidos"
              >
                <Trash size={16} />
              </button>
            ) : undefined
          }
        >
          <Stack align="stretch" gap="6">
            <Stack align="stretch" gap="2">
              <Input
                label="Agrega términos que serán excluidos de la anonimización"
                placeholder="Ingresa un término"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddWord()}
              />
              <Button variant="secondary" size="sm" onClick={handleAddWord}>
                Agregar término
              </Button>
            </Stack>
            {excludedWords.length > 0 && (
              <Stack p="1" bg="bg.secondary" rounded="xs" gap="1">
                {excludedWords.map((word) => (
                  <Label key={word} onRemove={() => handleRemoveWord(word)}>
                    {word}
                  </Label>
                ))}
              </Stack>
            )}
          </Stack>
        </LabelManagerSection>
        <Dialog open={clearDialogOpen} onOpenChange={setClearDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Borrar términos excluidos</DialogTitle>
            </DialogHeader>
            <DialogDescription>
              Esta acción no se puede deshacer. ¿Deseas continuar?
            </DialogDescription>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="secondary" size="sm">
                  Cancelar
                </Button>
              </DialogClose>
              <DialogClose asChild>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleClearAllWords}
                >
                  Borrar todos
                </Button>
              </DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </Stack>
    </TooltipProvider>
  );
}
