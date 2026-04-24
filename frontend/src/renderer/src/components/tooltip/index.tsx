import type { ReactNode } from "react";

import Arrow from "./Arrow";
import { Message, Tooltip as StyledTooltip, Wrapper } from "./Tooltip.styles";

export interface Props {
  children: ReactNode;
  text: string;
}
export default function Tooltip({ children, text }: Props) {
  return (
    // tabIndex = -1 because the only thing that can be focused is the children
    <Wrapper tabIndex={-1}>
      {children}
      <StyledTooltip role="tooltip">
        <Arrow />
        <Message>{text}</Message>
      </StyledTooltip>
    </Wrapper>
  );
}
