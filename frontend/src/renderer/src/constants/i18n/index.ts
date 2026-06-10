import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import es from "./locales/es";

// --- TypeScript type augmentation ---
// Tells i18next the exact shape of every namespace,
// so t('key') calls are fully typed and autocompleted.
declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "common";
    resources: typeof es;
  }
}

i18n.use(initReactI18next).init({
  lng: "es",
  fallbackLng: "es",
  defaultNS: "common",
  resources: {
    es,
  },
  interpolation: {
    escapeValue: false, // React already escapes values
  },
});

export default i18n;
