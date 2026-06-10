import {
  Children,
  type ReactElement,
  type ReactNode,
  cloneElement,
  isValidElement,
} from "react";

import type { Props as RadioProps } from "../radio";
import { Group, Legend } from "./RadioGroup.styles";

interface Props {
  children: ReactNode;
  label?: string;
  name: string;
  direction?: "horizontal" | "vertical";
}
export default function RadioGroup({
  label,
  name,
  direction = "horizontal",
  children,
}: Props) {
  // Inject the name to the children
  const radiosWithName = Children.map(children, (child) => {
    if (isValidElement(child)) {
      return cloneElement(child as ReactElement<RadioProps>, {
        name,
      });
    }
  });

  return (
    <Group direction={direction}>
      {label && <Legend>{label}</Legend>}
      {radiosWithName}
    </Group>
  );
}
