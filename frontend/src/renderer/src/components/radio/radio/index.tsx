import { Circle } from "phosphor-react";
import {
  type ChangeEventHandler,
  type ReactNode,
  forwardRef,
  useImperativeHandle,
  useRef,
} from "react";

import type { CSS } from "@/styles";
import { colors } from "@/styles/tokens";
import { Input, Radio as StyledRadio, Wrapper } from "./Radio.styles";

export interface Props {
  children?: ReactNode;
  name?: string;
  checked?: boolean;
  disabled?: boolean;
  onChange?: (value: boolean) => void;
  css?: CSS;
}
export default forwardRef<{ value: boolean }, Props>(function Radio(
  { name, checked = false, disabled = false, onChange, css, children },
  ref,
) {
  const inputRef = useRef<HTMLInputElement>(null);

  const hasText = !!children;

  // Only exposes `value` object to the parent component
  useImperativeHandle(
    ref,
    () => {
      return {
        value: inputRef.current?.checked ?? false,
      };
    },
    [],
  );

  const handleToggle: ChangeEventHandler<HTMLInputElement> = (e) => {
    onChange?.(e.target.checked);
  };

  const iconColor = disabled
    ? colors.textOnButtonDisabled
    : colors.textOnButtonAlternative;

  return (
    <Wrapper hasText={hasText} isDisabled={disabled} css={css}>
      <Input
        ref={inputRef}
        type="radio"
        name={name}
        defaultChecked={checked}
        disabled={disabled}
        onChange={handleToggle}
      />
      <StyledRadio>
        <Circle color={iconColor} weight="fill" />
      </StyledRadio>
      {children}
    </Wrapper>
  );
});
