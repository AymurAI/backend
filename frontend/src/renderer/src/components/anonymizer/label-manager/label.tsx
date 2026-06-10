import { css } from "@/styled/css";
import { HStack, styled } from "@/styled/jsx";
import { XCircle } from "phosphor-react";

interface LabelProps {
  children: string | string[];
  onRemove: () => void;
}
export function Label({ children, onRemove }: LabelProps) {
  return (
    <HStack
      justify="space-between"
      alignItems="center"
      px="1.5"
      py="0.5"
      bg="bg.primary-alternative"
      rounded="xs"
    >
      <styled.span textStyle="label.md.default">{children}</styled.span>
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Eliminar ${children}`}
        className={css({
          cursor: "pointer",
          color: "text.lighter",
          bg: "transparent",
          border: "none",
          display: "flex",
          flexShrink: "0",
          alignSelf: "center",
          p: "0",
          "&:hover": { color: "text.default" },
        })}
      >
        <XCircle size={14} />
      </button>
    </HStack>
  );
}
