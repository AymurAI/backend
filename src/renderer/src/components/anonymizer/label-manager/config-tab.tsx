import { HStack, Stack, styled } from "@/styled/jsx";
import { type AnonymizerLabels, anonymizerLabels } from "@/types/aymurai";
import { useState } from "react";

import Button from "@/components/ui/button";
import Input from "@/components/ui/input";
import BaseSwitch from "@/components/ui/switch";
import { EXCLUDED_TAGS } from "@/constants/excluded-tags";
import {
  useExcludedTagsConfig,
  useExcludedTagsConfigActions,
} from "@/store/useLocal";
import { Label } from "./label";
import LabelManagerSection from "./section";

interface ToggleProps {
  name: string;
  value: boolean;
  onToggle: (value: boolean) => void;
}
function Switch({ name, value, onToggle }: ToggleProps) {
  return (
    <styled.div px="4" py="3" bg="bg.secondary" rounded="xs">
      <HStack justify="space-between">
        <styled.span textStyle="label.md.default">{name}</styled.span>
        <BaseSwitch checked={value} onCheckedChange={onToggle} />
      </HStack>
    </styled.div>
  );
}

export default function LabelConfigTab() {
  const { tags: storedTags, words: storedWords } = useExcludedTagsConfig();
  const { setTags, setWords } = useExcludedTagsConfigActions();

  const [toggles, setToggles] = useState<Record<string, boolean>>(
    storedTags ?? EXCLUDED_TAGS,
  );
  const [excludedWords, setExcludedWords] = useState<string[]>(storedWords);
  const [inputValue, setInputValue] = useState("");

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

  return (
    <Stack gap="6" align="stretch">
      <LabelManagerSection title="Categorias incluidas">
        <Stack>
          {anonymizerLabels.map((label) => (
            <Switch
              key={label.id}
              name={label.text}
              value={toggles[label.id]}
              onToggle={(value) => handleToggle(label.id, value)}
            />
          ))}
        </Stack>
      </LabelManagerSection>
      <styled.hr borderColor="[#BCBAB8]" />
      <LabelManagerSection title="Términos excluidos">
        <Stack align="stretch" gap="6">
          <Stack align="stretch" gap="2">
            <Input
              label="Terminos excluidos"
              placeholder="Ingresa un termino"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddWord()}
            />
            <Button variant="secondary" size="sm" onClick={handleAddWord}>
              Agregar termino
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
    </Stack>
  );
}
