import type { KeyboardEventHandler, MouseEventHandler } from "react";

import * as S from "./Select.styles";
import type { SelectOption as Option } from "./index";

interface Props {
  options: Option[];
  onClick: (text: Option["text"]) => MouseEventHandler;
  onKeyDown: (text: Option["text"]) => KeyboardEventHandler;
}
export default function List({ options, onClick, onKeyDown }: Props) {
  const shouldRender = options.length > 0;

  if (!shouldRender) return null;

  return (
    <S.OptionContainer>
      {options.map(({ text, id }) => (
        <S.Option
          onClick={onClick(id)}
          onKeyDown={onKeyDown(id)}
          key={id}
          tabIndex={0}
        >
          {text}
        </S.Option>
      ))}
    </S.OptionContainer>
  );
}
