import { CheckCircle } from "phosphor-react";
import {
  Children,
  type FormEvent,
  type FormEventHandler,
  type ReactElement,
  type ReactNode,
  cloneElement,
  isValidElement,
  useEffect,
  useState,
} from "react";

import { Button, Subtitle } from "@/components";
import type { NativeComponent } from "@/types/component";

import { Form } from "./ValidationForm.styles";

interface Props extends NativeComponent<"form"> {
  children: ReactNode;
  title: string;
  onSubmit: FormEventHandler;
  onCheck: (checked: boolean) => void;
}
export default function ValidationForm({
  children,
  title,
  onSubmit,
  onCheck,
  ...props
}: Props) {
  const [checked, setChecked] = useState(false);

  const handleClick = () => setChecked(true);

  const onChange = () => {
    if (checked) setChecked(false);
  };

  // Add the onChange handler to every children
  const childrenWithHandler = Children.map(children, (child) => {
    if (isValidElement(child)) {
      return cloneElement(child as ReactElement, { onChange });
    }
    return child;
  });

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();

    onSubmit(e);
  };

  useEffect(() => {
    onCheck(checked);
  }, [checked, onCheck]);

  return (
    <Form {...props} onSubmit={handleSubmit}>
      <Subtitle weight="strong">{title}</Subtitle>
      {childrenWithHandler}
      <Button
        size="s"
        css={{ alignSelf: "flex-end" }}
        type="submit"
        onClick={handleClick}
        checked={checked}
      >
        Datos correctos
        {checked && <CheckCircle weight="fill" />}
      </Button>
    </Form>
  );
}
