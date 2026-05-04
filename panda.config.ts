import { defineConfig, defineGlobalStyles } from "@pandacss/dev";

const globalCss = defineGlobalStyles({
  "*": {
    fontFamily:
      '"Archivo", -apple-system, Helvetica Neue, Helvetica, Roboto, sans-serif', // TODO: Replace token here (was $primary)
  },

  html: {
    color: "#110041",
  },

  "mark.predicted-word": {
    backgroundColor: "#E6E8FF", // TODO: Replace token here (was $primaryAlt)
    fontFamily: '"Times New Roman", Times, serif', // TODO: Replace token here (was $file)
    padding: "0px 0px 0px 2px",
    borderRadius: "8px",

    "& strong": {
      fontSize: "12px",
      padding: "0px",
      margin: "0px",
    },

    "& button.remove-tag": {
      visibility: "hidden",
      position: "relative",
      backgroundColor: "#DC582E", // TODO: Replace token here (was $errorPrimary)
      color: "#FFFFFF", // TODO: Replace token here (was $white)
      padding: "3px 5px",
      borderRadius: "8px",
      cursor: "pointer",
      fontSize: "10px",
      fontWeight: 800, // TODO: Replace token here (was $heavy)
      textAlign: "center",
      top: "-10px",
      right: "-5px",
      border: "none",
    },

    "&:hover": {
      cursor: "pointer",
      "& button.remove-tag": {
        visibility: "visible",
      },
    },
  },

  "mark.searched-word": {
    backgroundColor: "#E0DDE2", // TODO: Replace token here (was $bgSecondaryAlt)
    fontFamily: '"Times New Roman", Times, serif', // TODO: Replace token here (was $file)
    padding: "0px 2px",
    borderRadius: "8px",

    "&:hover": {
      cursor: "pointer",
    },

    "& button.add-tag": {
      position: "relative",
      backgroundColor: "#1B834E", // TODO: Replace token here (was $successPrimary)
      color: "#FFFFFF", // TODO: Replace token here (was $white)
      padding: "2px 5px",
      borderRadius: "8px",
      cursor: "pointer",
      fontSize: "12px",
      fontWeight: 800, // TODO: Replace token here (was $heavy)
      textAlign: "center",
      top: "-10px",
      right: "-5px",
      border: "none",
    },
  },
});

const text = (size: number, weight: number, lineHeight: string) => ({
  value: {
    fontSize: `${size}px`,
    fontWeight: weight,
    lineHeight,
  },
});

const color = (hex: string) => ({ value: hex });

export default defineConfig({
  // Use CSS reset
  preflight: true,

  // Where to look for CSS declarations
  include: ["./src/renderer/src/**/*.{ts,tsx}"],

  // Files to exclude
  exclude: [],

  // JSX framework
  jsxFramework: "react",

  // Output directory for generated styled-system
  outdir: "src/renderer/src/styled",

  // Global styles (migrated from Stitches globalStyles.ts)
  globalCss,

  // Other configuration
  strictTokens: true,

  theme: {
    extend: {
      keyframes: {
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        fadeOut: {
          from: { opacity: "1" },
          to: { opacity: "0" },
        },
      },
      tokens: {
        animations: {
          fadeIn: { value: "fadeIn 0.15s ease-out" },
          fadeOut: { value: "fadeOut 0.1s ease-in" },
        },
      },
    },
    textStyles: {
      title: {
        md: {
          strong: text(32, 700, "120%"),
          default: text(32, 400, "120%"),
        },
      },
      subtitle: {
        md: {
          strong: text(20, 600, "120%"),
          default: text(20, 400, "120%"),
        },
        sm: {
          strong: text(14, 600, "120%"),
          default: text(14, 400, "120%"),
        },
      },
      paragraph: {
        md: {
          strong: text(18, 600, "150%"),
          default: text(18, 400, "150%"),
        },
        sm: {
          strong: text(16, 600, "140%"),
          default: text(16, 400, "140%"),
        },
        xsm: {
          strong: text(10, 600, "140%"),
          default: text(10, 400, "140%"),
        },
      },
      cta: {
        md: {
          strong: text(16, 600, "100%"),
          default: text(16, 400, "100%"),
        },
        sm: {
          strong: text(16, 600, "115%"),
          default: text(16, 400, "115%"),
        },
      },
      label: {
        md: {
          strong: text(16, 600, "120%"),
          default: text(16, 400, "120%"),
        },
        sm: {
          strong: text(12, 600, "120%"),
          default: text(12, 400, "120%"),
        },
      },
    },
    semanticTokens: {
      colors: {
        brand: {
          primary: color("#3F479D"),
          secondary: color("#C3CCD7"),
          tertiary: color("#4A5568"),
        },
        text: {
          default: color("#110041"),
          lighter: color("#625C68"),
          "onbutton-default": color("#110041"),
          "onbutton-alternative": color("#FFFFFF"),
          "onbutton-disabled": color("#2D3748"),
        },
        action: {
          default: color("#C5CAFF"),
          disabled: color("#E0DDE2"),
          "alt-default": color("#3F479D"),
          hover: color("#110041"),
          pressed: color("#3F479D"),
          focus: color("#C5CAFF"),
        },
        bg: {
          primary: color("#F6F5F7"),
          secondary: color("#FFFFFF"),
          "primary-alternative": color("#E5E8FF"),
          "primary-highlight": color("#C5CAFF"),
          "secondary-highlight": color("#E0DDE2"),
        },
        system: {
          success: color("#1B834E"),
          "success-secondary": color("#E0FAED"),
          error: color("#DC582E"),
          "error-secondary": color("#FFECE5"),
          warning: color("#F2BA2C"),
          "warning-secondary": color("#FFF7DB"),
          info: color("#3F479D"),
          "info-secondary": color("#F6F5F7"),
        },
      },
      borders: {
        primary: { value: "1px solid #BCBAB8" },
        secondary: { value: "1px solid #EDF2F7" },
        "primary-alt": { value: "1px solid #110041" },
        error: { value: "1px solid {colors.system.error}" },
      },
      gradients: {
        primary: {
          value:
            "linear-gradient(249.5deg, #C5CAFF -33.26%, #8591E8 28.49%, #3F479D 82.99%)",
        },
      },
    },
  },
});
