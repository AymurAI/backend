import {
  Children,
  type ReactElement,
  type ReactNode,
  cloneElement,
  isValidElement,
} from "react";

import type { Props as CheckboxProps } from "../checkbox";
import { Group, Legend } from "./CheckboxGroup.styles";

interface Props {
  children: ReactNode;
  title?: string;
  name: string;
  direction?: "horizontal" | "vertical";
}
export default function CheckboxGroup({
  title,
  name,
  direction = "horizontal",
  children,
}: Props) {
  // Inject the name to the children
  const checkboxWithName = Children.map(children, (child) => {
    if (isValidElement(child)) {
      return cloneElement(child as ReactElement<CheckboxProps>, {
        name,
      });
    }
  });

  return (
    <Group direction={direction}>
      {title && <Legend>{title}</Legend>}
      {checkboxWithName}
    </Group>
  );
}
