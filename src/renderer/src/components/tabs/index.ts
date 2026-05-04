import { styled } from "@/styles";

export const Tab = styled("div", {
  borderRadius: "$xxs",
  boxSizing: "border-box",

  display: "flex",
  flexDirection: "row",
  gap: "$s",
  alignItems: "center",

  p: "$m",

  fontSize: 16,

  variants: {
    status: {
      completed: {
        "& label, & span": {
          color: "$textOnButtonAlternative",
        },
        bg: "$actionPressed",
        b: "none",
      },
      focus: {
        "& label, & span": {
          color: "$textOnButtonDefault",
        },
        bg: "$actionFocus",
        boxShadow: "2px 2px 10px rgba(17, 0, 65, 0.25)",
        b: "1px solid $borderPrimaryAlt",
      },
      default: {
        "& label, & span": {
          color: "$textOnButtonDefault",
        },
        bg: "$primaryAlt",
        b: "none",
      },
    },
  },
  defaultVariants: {
    status: "default",
  },
});

export const TabName = styled("label", {
  textOverflow: "ellipsis",
  overflow: "hidden",
  whiteSpace: "nowrap",

  // width: 200,

  fontSize: "$labelMd",
  lineHeight: "$labelMd",
});
