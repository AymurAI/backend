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
      px="2"
      py="1"
      bg="bg.primary-alternative"
      rounded="xs"
    >
      <styled.span textStyle="label.md.default">{children}</styled.span>
      <styled.button
        type="button"
        onClick={onRemove}
        cursor="pointer"
        aria-label={`Eliminar ${children}`}
      >
        <XCircle size={16} />
      </styled.button>
    </HStack>
  );
}
