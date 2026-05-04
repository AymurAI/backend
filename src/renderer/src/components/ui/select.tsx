import * as RadixSelect from "@radix-ui/react-select";
import { CaretDown, CaretUp, Check } from "phosphor-react";
import { type Ref, useId, useImperativeHandle } from "react";

import Suggestion from "@/components/ui/suggestion";
import { sva } from "@/styled/css";
import { styled } from "@/styled/jsx";
import { stack } from "@/styled/patterns";

const Affix = styled("span", {
  base: {
    textStyle: "label.md.default",
    color: "text.lighter",
    flexShrink: "0",
  },
});

export type SelectOption = { id: string; text: string };
export type SelectSuggestion = { id: string; text?: string };

interface SelectProps {
  options: SelectOption[];
  label?: string;
  value?: string;
  onChange?: (value: SelectOption) => void;
  prefix?: string;
  suffix?: string;
  suggestion?: SelectSuggestion;
  priorityOrder?: string[];
  placeholder?: string;
  disabled?: boolean;
  size?: "md" | "sm";
  ref?: Ref<{ value: string | undefined }>;
}

function orderByPriority(options: SelectOption[], priority: string[] = []) {
  const filtered = options.filter(({ id }) => !priority.includes(id));
  const preferred = priority
    .map((p) => options.find(({ id }) => p === id))
    .filter((o): o is SelectOption => !!o);
  return [...preferred, ...filtered];
}

function secureSuggestion(
  suggestion: SelectSuggestion | undefined,
  options: SelectOption[],
): SelectOption | undefined {
  if (!suggestion) return undefined;
  if (suggestion.text) return { id: suggestion.id, text: suggestion.text };
  return options.find(({ id }) => id === suggestion.id);
}

const select = sva({
  slots: [
    "container",
    "trigger",
    "value",
    "caret",
    "content",
    "viewport",
    "item",
    "itemIndicator",
    "scrollButton",
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

      "[data-state='open'] &": {
        transform: "[rotate(180deg)]",
      },
    },
    content: {
      bg: "white",
      rounded: "sm",
      boxShadow: "[0px 8px 16px rgba(0, 0, 0, 0.08)]",
      border: "secondary",
      overflow: "hidden",
      zIndex: "10",
      minWidth: "[var(--radix-select-trigger-width)]",
    },
    viewport: {
      maxHeight: "[400px]",
      overflowY: "auto",
    },
    scrollButton: {
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      py: "1",
      color: "text.lighter",
      cursor: "default",
      bg: "white",
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
      "&[data-disabled]": {
        cursor: "not-allowed",
        color: "text.lighter",
      },
    },
    itemIndicator: {
      color: "brand.primary",
      display: "flex",
      alignItems: "center",
      flexShrink: "0",
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

export default function Select({
  options,
  label,
  value,
  onChange,
  prefix,
  suffix,
  suggestion,
  priorityOrder = [],
  placeholder = "",
  disabled = false,
  size = "md",
  ref,
}: SelectProps) {
  const triggerId = useId();
  const classes = select({ size });

  const orderedOptions = orderByPriority(options, priorityOrder);
  const securedSuggestion = secureSuggestion(suggestion, options);

  useImperativeHandle(ref, () => ({ value }), [value]);

  const handleChange = (id: string) => {
    const option = options.find((o) => o.id === id);
    if (option) onChange?.(option);
  };

  const handleSuggestionClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (securedSuggestion) handleChange(securedSuggestion.id);
  };

  const handleSuggestionKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.stopPropagation();
      if (securedSuggestion) handleChange(securedSuggestion.id);
    }
  };

  return (
    <div className={classes.container}>
      {label && (
        <styled.label
          textStyle="label.sm.default"
          color="text.lighter"
          htmlFor={triggerId}
        >
          {label}
        </styled.label>
      )}

      <RadixSelect.Root
        value={value}
        onValueChange={handleChange}
        disabled={disabled}
      >
        <RadixSelect.Trigger id={triggerId} asChild>
          {/* biome-ignore lint/a11y/useSemanticElements lint/a11y/useAriaPropsForRole: Radix merges role, aria-expanded, aria-controls, and tabIndex onto this div at runtime via asChild */}
          <div className={classes.trigger} role="combobox" tabIndex={0}>
            {prefix && <Affix aria-hidden="true">{prefix} |</Affix>}

            <RadixSelect.Icon asChild>
              <CaretDown size={16} className={classes.caret} aria-hidden="true" />
            </RadixSelect.Icon>

            <span className={classes.value}>
              {!value && securedSuggestion ? (
                <button
                  type="button"
                  onPointerDown={(e) => e.stopPropagation()}
                  onKeyDown={handleSuggestionKeyDown}
                  onClick={handleSuggestionClick}
                >
                  <Suggestion clickable>{securedSuggestion.text}</Suggestion>
                </button>
              ) : (
                <RadixSelect.Value placeholder={placeholder} />
              )}
            </span>

            {suffix && <Affix aria-hidden="true">| {suffix}</Affix>}
          </div>
        </RadixSelect.Trigger>

        <RadixSelect.Portal>
          <RadixSelect.Content
            className={classes.content}
            position="popper"
            sideOffset={4}
          >
            <RadixSelect.ScrollUpButton className={classes.scrollButton}>
              <CaretUp size={12} />
            </RadixSelect.ScrollUpButton>
            <RadixSelect.Viewport className={classes.viewport}>
              {orderedOptions.map(({ id, text }) => (
                <RadixSelect.Item key={id} value={id} className={classes.item}>
                  <RadixSelect.ItemIndicator className={classes.itemIndicator}>
                    <Check size={14} weight="bold" />
                  </RadixSelect.ItemIndicator>
                  <RadixSelect.ItemText>{text}</RadixSelect.ItemText>
                </RadixSelect.Item>
              ))}
            </RadixSelect.Viewport>
            <RadixSelect.ScrollDownButton className={classes.scrollButton}>
              <CaretDown size={12} />
            </RadixSelect.ScrollDownButton>
          </RadixSelect.Content>
        </RadixSelect.Portal>
      </RadixSelect.Root>
    </div>
  );
}
