import * as RadixSelect from "@radix-ui/react-select";
import { CaretDown, Check, MagnifyingGlass } from "phosphor-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import type { SelectOption } from "@/components/ui/select";
import {
  ANONYMIZER_CATEGORY_NAMES,
  getAnonymizerLabelsForCategory,
} from "@/constants/anonymizer-categories";
import { css, sva } from "@/styled/css";
import { styled } from "@/styled/jsx";
import { stack } from "@/styled/patterns";
import { normalizeEntityText } from "@/utils/anonymizer/entity-similarity";

interface AnonymizerLabelSelectProps {
  options: SelectOption[];
  value?: string;
  onChange?: (value: SelectOption) => void;
  onOpenChange?: (open: boolean) => void;
  placeholder?: string;
  disabled?: boolean;
  size?: "md" | "sm";
  currentCategory?: string;
}

interface LabelSection {
  category: string;
  labels: SelectOption[];
}

const select = sva({
  slots: [
    "container",
    "trigger",
    "value",
    "caret",
    "content",
    "search",
    "searchInput",
    "viewport",
    "groupLabel",
    "item",
    "itemIndicator",
    "empty",
  ],
  base: {
    container: { ...stack.raw({ gap: "1" }), width: "full" },
    trigger: {
      display: "flex",
      alignItems: "center",
      gap: "2",
      width: "full",
      bg: "white",
      border: "primary",
      rounded: "sm",
      cursor: "pointer",
      textAlign: "left",
      appearance: "none",
      textStyle: "label.md.default",
      color: "text.default",

      "&[data-state='open']": {
        boxShadow: "[0px 2px 2px rgba(0, 0, 0, 0.16)]",
        borderColor: "[#110041]",
      },
      "&:focus-visible": {
        outlineColor: "brand.primary",
        outlineWidth: "0.5",
        outlineStyle: "solid",
        outlineOffset: "0.5",
      },
      "&[data-disabled]": {
        bg: "bg.primary",
        cursor: "not-allowed",
        color: "text.lighter",
      },
      "&[data-placeholder]": {
        color: "text.lighter",
      },
    },
    value: {
      flex: "[1]",
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
    },
    caret: {
      flexShrink: "0",
      color: "text.default",
      transition: "[transform 0.15s ease]",

      "[data-state='open'] > &": {
        transform: "[rotate(180deg)]",
      },
    },
    content: {
      bg: "white",
      rounded: "sm",
      boxShadow: "[0px 8px 16px rgba(0, 0, 0, 0.08)]",
      border: "secondary",
      overflow: "hidden",
      zIndex: "50",
      minWidth: "[var(--radix-select-trigger-width)]",
    },
    search: {
      display: "flex",
      alignItems: "center",
      gap: "2",
      px: "3",
      py: "2",
      borderBottom: "[1px solid #E5E1DD]",
      color: "text.lighter",
    },
    searchInput: {
      width: "full",
      minW: "0",
      outline: "none",
      color: "text.default",
      textStyle: "label.md.default",
      "&::placeholder": {
        color: "text.lighter",
      },
    },
    viewport: {
      maxHeight: "[360px]",
      overflowY: "auto",
      py: "1",
    },
    groupLabel: {
      px: "3",
      pt: "3",
      pb: "1",
      textStyle: "label.sm.default",
      color: "text.lighter",
      textTransform: "uppercase",
    },
    item: {
      display: "flex",
      alignItems: "center",
      gap: "2",
      textStyle: "label.md.default",
      color: "text.default",
      cursor: "pointer",
      outline: "none",
      userSelect: "none",

      "&[data-highlighted]": {
        bg: "bg.primary-alternative",
      },
      "&[data-state='checked']": {
        bg: "bg.primary-alternative",
      },
    },
    itemIndicator: {
      color: "brand.primary",
      display: "flex",
      alignItems: "center",
      flexShrink: "0",
    },
    empty: {
      px: "3",
      py: "4",
      textStyle: "label.md.default",
      color: "text.lighter",
    },
  },
  variants: {
    size: {
      md: {
        trigger: { px: "3", py: "3" },
        item: { px: "3", py: "3" },
      },
      sm: {
        trigger: { px: "3", py: "1" },
        item: { px: "3", py: "3" },
      },
    },
  },
  defaultVariants: {
    size: "md",
  },
});

const technicalId = css({
  color: "text.lighter",
  textStyle: "label.sm.default",
  whiteSpace: "nowrap",
});

function labelMatches(option: SelectOption, query: string) {
  const normalizedQuery = normalizeEntityText(query);
  if (!normalizedQuery) return true;

  const haystacks = [option.id, option.text, option.shortText ?? ""]
    .map((value) => normalizeEntityText(value))
    .filter(Boolean);

  if (haystacks.some((value) => value.includes(normalizedQuery))) return true;

  const labelTokens = haystacks.flatMap((value) => value.split(" "));
  return normalizedQuery
    .split(" ")
    .every((queryToken) =>
      labelTokens.some((labelToken) => labelToken.includes(queryToken)),
    );
}

function buildSections(
  options: SelectOption[],
  query: string,
  currentCategory?: string,
): LabelSection[] {
  const optionById = new Map(options.map((option) => [option.id, option]));
  const seen = new Set<string>();
  const categories = currentCategory
    ? [
        currentCategory,
        ...ANONYMIZER_CATEGORY_NAMES.filter(
          (category) => category !== currentCategory,
        ),
      ]
    : ANONYMIZER_CATEGORY_NAMES;

  return categories
    .map((category) => {
      const labels = getAnonymizerLabelsForCategory(category)
        .map((label) => optionById.get(label.id))
        .filter((label): label is SelectOption => !!label)
        .filter((label) => {
          if (seen.has(label.id)) return false;
          return labelMatches(label, query);
        });

      labels.forEach((label) => seen.add(label.id));

      return { category, labels };
    })
    .filter((section) => section.labels.length > 0);
}

export default function AnonymizerLabelSelect({
  options,
  value,
  onChange,
  onOpenChange,
  placeholder = "",
  disabled = false,
  size = "md",
  currentCategory,
}: AnonymizerLabelSelectProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const triggerId = useId();
  const searchInputRef = useRef<HTMLInputElement>(null);
  const classes = select({ size });

  const selectedOption = options.find((option) => option.id === value);
  const sections = useMemo(
    () => buildSections(options, query, currentCategory),
    [currentCategory, options, query],
  );

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(
      () => searchInputRef.current?.focus({ preventScroll: true }),
      0,
    );
    return () => window.clearTimeout(timer);
  }, [open]);

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    onOpenChange?.(nextOpen);
    if (!nextOpen) setQuery("");
  };

  const handleChange = (id: string) => {
    const option = options.find((item) => item.id === id);
    if (option) onChange?.(option);
  };

  return (
    <div className={classes.container}>
      <RadixSelect.Root
        value={value}
        onValueChange={handleChange}
        onOpenChange={handleOpenChange}
        disabled={disabled}
      >
        <RadixSelect.Trigger id={triggerId} asChild>
          {/* biome-ignore lint/a11y/useSemanticElements lint/a11y/useAriaPropsForRole: Radix merges role, aria-expanded, aria-controls, and tabIndex onto this div at runtime via asChild */}
          <div className={classes.trigger} role="combobox" tabIndex={0}>
            <span className={classes.value}>
              {selectedOption?.shortText ?? selectedOption?.text ?? placeholder}
            </span>
            <RadixSelect.Icon asChild>
              <CaretDown
                size={16}
                className={classes.caret}
                aria-hidden="true"
              />
            </RadixSelect.Icon>
          </div>
        </RadixSelect.Trigger>

        <RadixSelect.Portal>
          <RadixSelect.Content
            className={classes.content}
            position="popper"
            sideOffset={4}
          >
            <div className={classes.search}>
              <MagnifyingGlass size={16} />
              <input
                ref={searchInputRef}
                className={classes.searchInput}
                placeholder="Buscar etiqueta"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  window.requestAnimationFrame(() =>
                    searchInputRef.current?.focus({ preventScroll: true }),
                  );
                }}
                onPointerDown={(event) => event.stopPropagation()}
                onKeyDownCapture={(event) => {
                  if (event.key !== "Escape") event.stopPropagation();
                }}
                onKeyDown={(event) => {
                  if (event.key !== "Escape") event.stopPropagation();
                }}
              />
            </div>
            <RadixSelect.Viewport className={classes.viewport}>
              {sections.length === 0 ? (
                <div className={classes.empty}>Sin resultados</div>
              ) : (
                sections.map((section) => (
                  <RadixSelect.Group key={section.category}>
                    <RadixSelect.Label className={classes.groupLabel}>
                      {section.category}
                    </RadixSelect.Label>
                    {section.labels.map((option) => (
                      <RadixSelect.Item
                        key={option.id}
                        value={option.id}
                        className={classes.item}
                      >
                        <RadixSelect.ItemIndicator
                          className={classes.itemIndicator}
                        >
                          <Check size={14} weight="bold" />
                        </RadixSelect.ItemIndicator>
                        <RadixSelect.ItemText>
                          <styled.span>{option.text}</styled.span>
                        </RadixSelect.ItemText>
                        <span className={technicalId}>{option.id}</span>
                      </RadixSelect.Item>
                    ))}
                  </RadixSelect.Group>
                ))
              )}
            </RadixSelect.Viewport>
          </RadixSelect.Content>
        </RadixSelect.Portal>
      </RadixSelect.Root>
    </div>
  );
}
