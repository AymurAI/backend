const common = {
  back: "Volver",
  howItWorks: "¿Cómo funciona?",
  platformBuiltBy: "Plataforma hecha por",
  home: {
    features: {
      greeting: "¡Hola! Selecciona la herramienta a utilizar",
    },
    host: {
      howToConnect: "¿Como deseas conectarte a Aymurai?",
      optionLocal: "Local",
      optionServer: "Servidor",
      optionOr: "o",
      connectServerExplanation:
        "Ingresa la dirección del servidor al que deseas conectarte",
      connectServerLabel: "Direccion del servidor",
      connectServerSubmit: "Guardar y conectar",
      errors: {
        network: "No se pudo conectar al servidor",
        connection: "Error de conexión",
        invalidResponse: "El servidor no respondió correctamente",
        invalidUrl: "El formato de la URL es incorrecto.",
        unknown: "Error desconocido",
      },
    },
  },
  stepper: {
    selection: "Selección",
    extraction: "Extracción",
    validation: "Validación",
    finalization: "Finalización",
  },
  howItWorksSteps: {
    step1: {
      alt: "Interfaz web con selector y cursor",
      title: "Selecciona las resoluciones judiciales",
      subtitle: "Sube los documentos que querés incorporar al set de datos.",
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
        "Es importante que verifiques que los datos sean correctos antes de exportar el archivo",
    },
  },
  filePreview: {
    loadError: "No se pudo cargar el archivo",
  },
};

export default common;
