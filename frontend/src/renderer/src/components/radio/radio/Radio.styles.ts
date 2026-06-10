import { styled } from "@/styles";

export const Input = styled("input", {
  position: "absolute",
  top: 0,
  left: 0,

  opacity: 0,
});

export const Radio = styled("div", {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",

  width: 18,
  height: 18,
  p: 1,

  borderRadius: "100%",
  boxSizing: "border-box",
});

export const Wrapper = styled("label", {
  // Unchecked
  $$radio_bg_default: "$colors$white",
  $$radio_border_default: "$sizes$xxs solid $colors$actionDefaultAlt",
  // hover
  $$radio_bgHover_default: "$colors$white",
  $$radio_borderHover_default: "1px solid $colors$borderPrimary",
  // disabled
  $$radio_bgDisabled_default: "$colors$actionDisabled",
  $$radio_borderDisabled_default: "$sizes$xxs solid $colors$borderPrimary",
  // focus
  $$radio_bgFocus_default: "$colors$white",
  $$radio_borderFocus_default: "1px solid $colors$borderPrimary",

  // Checked
  $$radio_bg_checked: "$colors$actionDefaultAlt",
  $$radio_border_checked: "5px solid $colors$actionDefaultAlt",
  // hover
  $$radio_bgHover_checked: "$colors$actionHover",
  $$radio_borderHover_checked: "5px solid $colors$actionHover",
  // disabled
  $$radio_bgDisabled_checked: "$colors$actionDisabled",
  $$radio_borderDisabled_checked: "none",
  // focus
  $$radio_bgFocus_checked: "$colors$actionDefaultAlt",
  $$radio_borderFocus_checked: "5px solid $colors$actionDefaultAlt",

  // Focus
  $$radio_outlineFocus_noText: "3px solid $colors$borderPrimaryAlt",
  $$radio_outlineFocus_Text: "3px solid $colors$borderPrimary",

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
          outline: "$$radio_outlineFocus_Text",
          borderRadius: "3px",
        },
      },
      false: {
        "&:focus-within": {
          outline: "$$radio_outlineFocus_noText",
          borderRadius: "100%",
        },
        // Focus for radio
        [`& > input:checked:focus-visible + ${Radio}`]: {
          bg: "$$radio_bgFocus_checked",
          b: "$$radio_borderFocus_checked",
        },
        [`& > input:focus-visible + ${Radio}`]: {
          bg: "$$radio_bgFocus_default",
          b: "$$radio_borderFocus_default",
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
    hasText: "false",
    isDisabled: "false",
  },

  // Radio styles
  [`& > ${Radio}`]: {
    b: "$$radio_border_default",
    bg: "$$radio_bg_default",
  },
  [`& > input:checked + ${Radio}`]: {
    bg: "$$radio_bg_checked",
    border: "$$radio_border_checked",
  },

  // Hide SVG when unchecked
  [`& > input:not(:checked) + ${Radio} svg`]: {
    display: "none",
  },

  // Hover
  [`&:hover > ${Radio}`]: {
    b: "$$radio_borderHover_default",
    bg: "$$radio_bgHover_default",
  },
  [`&:hover > input:checked + ${Radio}`]: {
    b: "$$radio_borderHover_checked",
    bg: "$$radio_bgHover_checked",
  },

  // Disabled
  [`& > input:disabled + ${Radio}`]: {
    bg: "$$radio_bgDisabled_default",
    b: "$$radio_borderDisabled_default",
  },
  [`& > input:checked:disabled + ${Radio}`]: {
    bg: "$$radio_bgDisabled_checked",
    b: "$$radio_borderDisabled_checked",
  },
});
