import { globalCss } from "./stitches.config";

export const globalStyles = globalCss({
  "@import":
    'url("https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;800&display=swap")',

  "html, body, div, span, applet, object, iframe, h1, h2, h3, h4, h5, h6, p, blockquote, pre, a, abbr, acronym, address, big, cite, code, del, dfn, em, img, ins, kbd, q, s, samp, small, strike, strong, sub, sup, tt, var, b, u, i, center, dl, dt, dd, ol, ul, li, fieldset, form, label, legend, table, caption, tbody, tfoot, thead, tr, th, td, article, aside, canvas, details, embed, figure, figcaption, footer, header, hgroup, main, menu, nav, output, ruby, section, summary, time, mark, audio, video":
    {
      margin: "0",
      padding: "0",
      border: "0",
      verticalAlign: "baseline",
      boxSizing: "border-box",
      color: "$tertiary",
    },

  "*": {
    fontFamily: "$primary",
  },

  "mark.predicted-word": {
    backgroundColor: "$primaryAlt",

    fontFamily: "$file",

    padding: "0px 0px 0px 2px",

    borderRadius: 8,
    "& strong": {
      fontSize: "12px",
      padding: "0px",
      margin: "0px",
    },
    "& button.remove-tag": {
      visibility: "hidden",
      position: "relative",
      backgroundColor: "$errorPrimary",
      color: "$white",
      padding: "3px 5px",
      borderRadius: 8,
      cursor: "pointer",
      fontSize: "10px",
      fontWeight: "heavy",
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
    backgroundColor: "$bgSecondaryAlt",

    fontFamily: "$file",

    padding: "0px 2px",

    borderRadius: 8,

    "&:hover": {
      cursor: "pointer",
    },

    "& button.add-tag": {
      position: "relative",
      backgroundColor: "$successPrimary",
      color: "$white",
      padding: "2px 5px",
      borderRadius: 8,
      cursor: "pointer",
      fontSize: "12px",
      fontWeight: "heavy",
      textAlign: "center",
      top: "-10px",
      right: "-5px",
      border: "none",
    },
  },
});
