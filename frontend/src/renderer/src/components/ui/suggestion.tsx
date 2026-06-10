import { styled } from "@/styled/jsx";

const Suggestion = styled("mark", {
  base: {
    bg: "bg.primary-alternative",
    textStyle: "label.md.default",
    display: "inline-flex",
  },
  variants: {
    clickable: {
      true: { cursor: "pointer" },
      false: { cursor: "unset" },
    },
    rounded: {
      true: { rounded: "md" },
      false: { rounded: "[0px]" },
    },
  },
  defaultVariants: {
    clickable: false,
    rounded: false,
  },
});

export default Suggestion;
