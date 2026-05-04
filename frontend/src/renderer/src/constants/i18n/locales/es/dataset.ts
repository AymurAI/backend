import { WHITELISTED_EXTENSIONS } from "@/constants/config";

const dataset = {
  title: "Set de datos",
  subtitle: "Convertí resoluciones judiciales en set de datos estructurados",
  onboarding: {
    sectionTitle: "1. Selección de Archivos",
    validFormats: "Formatos válidos: .doc y .docx",
    loadDocuments: "Cargar documentos",
    dropAreaTitle: "Selecciona el archivo para\nagregar a la base de datos",
    dropAreaFormats: `Formatos válidos: ${WHITELISTED_EXTENSIONS.map((e) => `.${e}`).join(", ")}`,
  },
  preview: {
    sectionTitle: "1. Selección de Archivos",
    filesLabel: "Archivos seleccionados",
    validFormats: "Formatos válidos: .doc y .docx",
    loadMore: "Cargar más documentos",
    continue: "Continuar",
  },
  howItWorks: {
    step4: {
      alt: "Binoculares con globo terráqueo",
      title: "Generación del set de datos",
      subtitle:
        "Los documentos pasan a formar parte del set de datos abiertos.",
    },
  },
  process: {
    sectionTitle: "2. Extracción de datos",
    processingTitle: "AymurAI está extrayendo los datos de los archivos",
    processingSubtitle: "Este proceso puede tardar algunos minutos.",
    finishText: "Se finalizó el análisis de tus documentos.",
  },
  result: { sectionTitle: "" },
  finish: {
    sectionTitle: "4. Finalización",
    description:
      "Los datos encontrados por AymurAI y posteriormente validados ya son parte del set de datos abiertos con perspectiva de género.",
    subtitle: "Archivos procesados",
    restart: "Cargar más documentos",
    viewResult: "Ver set de datos",
  },
};

export default dataset;
