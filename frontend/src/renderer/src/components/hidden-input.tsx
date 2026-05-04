import { WHITELISTED_EXTENSIONS } from "@/constants/config";
import { css, cx } from "@/styled/css";
import type { ComponentProps } from "react";

const input = css({
  display: "none",
  visibility: "hidden",
  opacity: 0,
  pointerEvents: "none",
});

interface HiddenInputProps extends Omit<ComponentProps<"input">, "onChange"> {
  onChange: React.ChangeEventHandler<HTMLInputElement>;
}
export default function HiddenInput({ className, ...props }: HiddenInputProps) {
  // Convert the array into a '.dcox' form
  const extensions = WHITELISTED_EXTENSIONS.map((ext) => `.${ext}`).join(",");
  return (
    <input
      type="file"
      accept={extensions}
      tabIndex={-1}
      className={cx(input, className)}
      {...props}
    />
  );
}
