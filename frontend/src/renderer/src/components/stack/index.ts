import { styled } from "@/styles";

const Stack = styled("div", {
  display: "flex",

  variants: {
    direction: {
      row: { flexDirection: "row" },
      column: { flexDirection: "column" },
      "row-reverse": { flexDirection: "row-reverse" },
      "column-reverse": { flexDirection: "column-reverse" },
    },

    wrap: {
      wrap: { flexWrap: "wrap" },
      nowrap: { flexWrap: "nowrap" },
      "wrap-reverse": { flexWrap: "wrap-reverse" },
    },

    justify: {
      start: { justifyContent: "start" },
      end: { justifyContent: "end" },
      center: { justifyContent: "center" },
      "space-between": { justifyContent: "space-between" },
      "space-around": { justifyContent: "space-around" },
      "space-evenly": { justifyContent: "space-evenly" },
    },

    align: {
      start: { alignItems: "start" },
      end: { alignItems: "end" },
      center: { alignItems: "center" },
      stretch: { alignItems: "stretch" },
      baseline: { alignItems: "baseline" },
    },

    spacing: {
      none: { gap: 0 },
      xxs: { gap: "$xxs" },
      xs: { gap: "$xs" },
      s: { gap: "$s" },
      m: { gap: "$m" },
      l: { gap: "$l" },
      xl: { gap: "$xl" },
    },
    textColor: {
      default: {
        color: "$textDefault",
      },
    },
  },

  defaultVariants: {
    direction: "row",
    wrap: "wrap",
    justify: "start",
    align: "start",
    spacing: "s",
    textColor: "default",
  },
});

export default Stack;
