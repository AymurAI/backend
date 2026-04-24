import { type CSS as CSSProp, createStitches } from "@stitches/react";

import * as tokens from "./tokens";

export const defaultTheme = createStitches({
  theme: {
    colors: {
      ...tokens.colors,
    },
    fonts: tokens.fonts,
    fontSizes: tokens.fontSizes,
    fontWeights: tokens.fontWeights,
    letterSpacings: {},
    lineHeights: tokens.lineHeights,
    radii: tokens.radii,
    shadows: {},
    sizes: tokens.sizes,
    space: tokens.spaces,
    transitions: tokens.transitions,
  },
  utils: {
    // ----------------
    // PADDINGS
    // ----------------
    p: (value: number | string) => ({
      padding: value,
    }),
    pt: (value: number | string) => ({
      paddingTop: value,
    }),
    pr: (value: number | string) => ({
      paddingRight: value,
    }),
    pb: (value: number | string) => ({
      paddingBottom: value,
    }),
    pl: (value: number | string) => ({
      paddingLeft: value,
    }),
    px: (value: number | string) => ({
      paddingLeft: value,
      paddingRight: value,
    }),
    py: (value: number | string) => ({
      paddingTop: value,
      paddingBottom: value,
    }),

    // ----------------
    // MARGINS
    // ----------------
    m: (value: number | string) => ({
      margin: value,
    }),
    mt: (value: number | string) => ({
      marginTop: value,
    }),
    mr: (value: number | string) => ({
      marginRight: value,
    }),
    mb: (value: number | string) => ({
      marginBottom: value,
    }),
    ml: (value: number | string) => ({
      marginLeft: value,
    }),
    mx: (value: number | string) => ({
      marginLeft: value,
      marginRight: value,
    }),
    my: (value: number | string) => ({
      marginTop: value,
      marginBottom: value,
    }),

    // ----------------
    // BORDER
    // ----------------
    b: (value: string) => ({
      border: value,
    }),
    bt: (value: string) => ({
      borderTop: value,
    }),
    br: (value: string) => ({
      borderRight: value,
    }),
    bb: (value: string) => ({
      borderBottom: value,
    }),
    bl: (value: string) => ({
      borderLeft: value,
    }),
    bx: (value: string) => ({
      borderLeft: value,
      borderRight: value,
    }),
    by: (value: string) => ({
      borderTop: value,
      borderBottom: value,
    }),

    // ----------------
    // BACKGROUND
    // ----------------
    bg: (value: string) => ({
      backgroundColor: value,
    }),
  },
  media: {
    sm: "(min-width: 640px)",
    md: "(min-width: 768px)",
    lg: "(min-width: 1024px)",
    xl: "(min-width: 1280px)",
  },
});

export type CSS = CSSProp<typeof defaultTheme>;

export const { styled, globalCss, createTheme, theme, keyframes } =
  defaultTheme;
