import { styled } from "@/styles";

function columnRepeat(cols: number) {
  return {
    gridTemplateColumns: `repeat(${cols}, 1fr)`,
  };
}

function rowRepeat(rows: number) {
  return {
    gridTemplateRows: `repeat(${rows}, 1fr)`,
  };
}

const Grid = styled("div", {
  display: "grid",

  variants: {
    columns: {
      none: {},
      1: columnRepeat(1),
      2: columnRepeat(2),
      3: columnRepeat(3),
      4: columnRepeat(4),
      5: columnRepeat(5),
      6: columnRepeat(6),
      7: columnRepeat(7),
      8: columnRepeat(8),
      9: columnRepeat(9),
      10: columnRepeat(10),
      11: columnRepeat(11),
      12: columnRepeat(12),
    },

    rows: {
      none: {},
      1: rowRepeat(1),
      2: rowRepeat(2),
      3: rowRepeat(3),
      4: rowRepeat(4),
      5: rowRepeat(5),
      6: rowRepeat(6),
      7: rowRepeat(7),
      8: rowRepeat(8),
      9: rowRepeat(9),
      10: rowRepeat(10),
      11: rowRepeat(11),
      12: rowRepeat(12),
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

    align: {
      start: { alignItems: "start" },
      end: { alignItems: "end" },
      center: { alignItems: "center" },
      stretch: { alignItems: "stretch" },
      baseline: { alignItems: "baseline" },
    },

    justify: {
      start: { justifyItems: "start" },
      end: { justifyItems: "end" },
      center: { justifyItems: "center" },
      stretch: { justifyItems: "stretch" },
    },
  },
  defaultVariants: {
    columns: "none",
    rows: "none",
    spacing: "s",
    align: "start",
    justify: "start",
  },
});

export default Grid;
