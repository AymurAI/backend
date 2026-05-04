import { WHITELISTED_EXTENSIONS } from "@/constants/config";

const anonymizer = {
  title: "Anonimizador",
  subtitle: "Anonimiza resoluciones judiciales de manera automática y editable",
  onboarding: {
    sectionTitle: "1. Selección de Archivo",
    validFormats: "Formatos válidos: .doc y .docx",
    loadDocuments: "Cargar documentos",
    dropAreaTitle: "Selecciona el archivo para anonimizar",
    dropAreaFormats: `Formatos válidos: ${WHITELISTED_EXTENSIONS.map((e) => `.${e}`).join(", ")}`,
  },
  preview: {
    sectionTitle: "1. Selección de Archivo",
    filesLabel: "Archivos seleccionados",
    validFormats: "Formatos válidos: .doc y .docx",
    loadMore: "Cargar más documentos",
    continue: "Continuar",
  },
  howItWorks: {
    step4: {
      alt: "Binoculares con globo terráqueo",
      title: "Generación del documento anonimizado",
      subtitle:
        "Proceso terminado. El documento esta listo para ser exportado.",
    },
  },
  process: {
    sectionTitle: "2. Procesamiento del archivo",
    processingTitle: "AymurAI está extrayendo los datos del archivo",
    processingSubtitle: "Este proceso puede tardar algunos minutos.",
    finishText: "Se finalizó el análisis del documento.",
  },
  validation: {
    toastSingleSuccess:
      'Se aplicó con éxito una etiqueta de "{{label}}" en una ocurrencia.',
    toastAllSuccess:
      'Se aplicó con éxito una etiqueta de "{{label}}" en todas las ocurrencias.',
  },
  result: { sectionTitle: "" },
  finish: {
    sectionTitle: "4. Finalización",
    description:
      "Los datos encontrados por AymurAI y posteriormente validados ya han sido anonimizados correctamente.",
    subtitle: "Archivo procesado",
    restart: "Cargar un nuevo documento",
    viewResult: "Descargar ODT",
    viewResultPDF: "Descargar PDF",
  },
};

export default anonymizer;
