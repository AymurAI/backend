import { WHITELISTED_EXTENSIONS } from "@/constants/config";

const validExtensions = WHITELISTED_EXTENSIONS.map((e) => `.${e}`).join(", ");

const dataset = {
  title: "Set de datos",
  subtitle: "Convierte resoluciones judiciales en set de datos estructurados",
  onboarding: {
    sectionTitle: "1. Selección de Archivos",
    validFormats: `Formatos válidos: ${validExtensions}`,
    loadDocuments: "Cargar documentos",
    dropAreaTitle: "Selecciona el archivo para\nagregar a la base de datos",
    dropAreaFormats: `Formatos válidos: ${validExtensions}`,
  },
  preview: {
    sectionTitle: "1. Selección de Archivos",
    filesLabel: "Archivos seleccionados",
    validFormats: `Formatos válidos: ${validExtensions}`,
    loadMore: "Cargar más documentos",
    continue: "Continuar",
  },
  howItWorks: {
    step1: {
      alt: "Interfaz web con selector y cursor",
      title: "Selecciona las resoluciones judiciales",
      subtitle: "Sube los documentos que quieres incorporar al set de datos.",
    },
    step2: {
      alt: "Barra de búsqueda con cursor",
      title: "La inteligencia artificial analiza los documentos",
      subtitle:
        "Extrae automáticamente la información relevante de cada documento.",
    },
    step3: {
      alt: "Visor de documentos con controles de revisión",
      title: "Revisión y validación humana",
      subtitle:
        "Es importante que verifiques que los datos sean correctos antes de exportar el archivo.",
    },
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
