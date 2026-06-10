import { styled } from "@/styles";

export const Input = styled("input", {
  position: "absolute",
  top: 0,
  left: 0,

  opacity: 0,
});

export const Checkbox = styled("div", {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",

  width: 18,
  height: 18,
  p: 1,

  borderRadius: "$xs",
  boxSizing: "border-box",
});

export const Wrapper = styled("label", {
  // Unchecked
  $$checkbox_bg_default: "$colors$white",
  $$checkbox_border_default: "$sizes$xxs solid $colors$actionDefaultAlt",
  // hover
  $$checkbox_bgHover_default: "$colors$white",
  $$checkbox_borderHover_default: "1px solid $colors$borderPrimary",
  // disabled
  $$checkbox_bgDisabled_default: "$colors$actionDisabled",
  $$checkbox_borderDisabled_default: "$sizes$xxs solid $colors$borderPrimary",
  // focus
  $$checkbox_bgFocus_default: "$colors$white",
  $$checkbox_borderFocus_default: "1px solid $colors$borderPrimary",

  // Checked
  $$checkbox_bg_checked: "$colors$actionDefaultAlt",
  $$checkbox_border_checked: "none",
  // hover
  $$checkbox_bgHover_checked: "$colors$actionHover",
  $$checkbox_borderHover_checked: "none",
  // disabled
  $$checkbox_bgDisabled_checked: "$colors$actionDisabled",
  $$checkbox_borderDisabled_checked: "none",
  // focus
  $$checkbox_bgFocus_checked: "$colors$actionDefaultAlt",
  $$checkbox_borderFocus_checked: "none",

  // Focus
  $$checkbox_outlineFocus_noText: "3px solid $colors$borderPrimaryAlt",
  $$checkbox_outlineFocus_Text: "3px solid $colors$borderPrimary",

  position: "relative",

  display: "flex",
  flexDirection: "row",
  alignItems: "center",
  gap: "$s",

  transitionDuration: "$transitions$s",
  transitionProperty: "outline, border-radius, border",
  transitionTimingFunction: "ease",

  variants: {
    hasText: {
      true: {
        p: "$s",
        "&:focus-within": {
          outline: "$$checkbox_outlineFocus_Text",
          borderRadius: "3px",
        },
      },
      false: {
        "&:focus-within": {
          outline: "$$checkbox_outlineFocus_noText",
          borderRadius: "$xs",
        },
        // Focus for checkbox
        [`& > input:checked:focus-visible + ${Checkbox}`]: {
          bg: "$$checkbox_bgFocus_checked",
          b: "$$checkbox_borderFocus_checked",
        },
        [`& > input:focus-visible + ${Checkbox}`]: {
          bg: "$$checkbox_bgFocus_default",
          b: "$$checkbox_borderFocus_default",
        },
      },
    },
    isDisabled: {
      true: {
        "&, & > *": {
          cursor: "not-allowed",
        },
      },
      false: {
        "&, & > *": {
          cursor: "pointer",
        },
      },
    },
  },
  defaultVariants: {
    hasText: false,
    isDisabled: false,
  },

  // Checkbox styles
  [`& > ${Checkbox}`]: {
    b: "$$checkbox_border_default",
    bg: "$$checkbox_bg_default",
  },
  [`& > input:checked + ${Checkbox}`]: {
    bg: "$$checkbox_bg_checked",
    border: "$$checkbox_border_checked",
  },

  // Hide SVG when unchecked
  [`& > input:not(:checked) + ${Checkbox} svg`]: {
    display: "none",
  },

  // Hover
  [`&:hover > ${Checkbox}`]: {
    b: "$$checkbox_borderHover_default",
    bg: "$$checkbox_bgHover_default",
  },
  [`&:hover > input:checked + ${Checkbox}`]: {
    b: "$$checkbox_borderHover_checked",
    bg: "$$checkbox_bgHover_checked",
  },

  // Disabled
  [`& > input:disabled + ${Checkbox}`]: {
    bg: "$$checkbox_bgDisabled_default",
    b: "$$checkbox_borderDisabled_default",
  },
  [`& > input:checked:disabled + ${Checkbox}`]: {
    bg: "$$checkbox_bgDisabled_checked",
    b: "$$checkbox_borderDisabled_checked",
  },
});
