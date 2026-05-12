import { WHITELISTED_EXTENSIONS } from "@/constants/config";

const validExtensions = WHITELISTED_EXTENSIONS.map((e) => `.${e}`).join(", ");

const anonymizer = {
  title: "Anonimizador",
  subtitle: "Anonimiza resoluciones judiciales de manera automática y editable",
  onboarding: {
    sectionTitle: "1. Selección de Archivo",
    validFormats: `Formatos válidos: ${validExtensions}`,
    loadDocuments: "Cargar documentos",
    dropAreaTitle: "Selecciona el archivo para anonimizar",
    dropAreaFormats: `Formatos válidos: ${validExtensions}`,
  },
  preview: {
    sectionTitle: "1. Selección de Archivo",
    filesLabel: "Archivos seleccionados",
    validFormats: `Formatos válidos: ${validExtensions}`,
    loadMore: "Cargar más documentos",
    continue: "Continuar",
  },
  howItWorks: {
    step1: {
      alt: "Interfaz web con selector y cursor",
      title: "Selecciona la resolución judicial",
      subtitle: "Sube el documento que quieres anonimizar.",
    },
    step2: { 
      alt: "Barra de búsqueda con cursor",
      title: "La inteligencia artificial analiza el documento",
      subtitle:
        "Reconoce automáticamente la información a anonimizar.",
    },
    step3: {
      alt: "Visor de documentos con controles de revisión",
      title: "Revisión y validación humana",
      subtitle:
        "Es importante que verifiques que los datos sean correctos antes de exportar el archivo.",
    },
    step4: {
      alt: "Binoculares con globo terráqueo",
      title: "Generación del documento anonimizado",
      subtitle:
        "Proceso terminado. El documento está listo para ser exportado.",
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
    downloadError:
      "Ocurrió un error al generar el archivo. Por favor, intente nuevamente.",
  },
};

export default anonymizer;
