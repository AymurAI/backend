import {
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { useRef } from "react";

import { useFileDispatch } from "@/hooks";
import { addFiles } from "@/reducers/file/actions";

import {
  Button,
  HiddenInput,
  OnboardingCard,
  OnboardingGrid,
  Stack,
  Text,
  Title,
} from "@/components";
import { Footer, Section } from "@/layout/main";
import { Feature } from "@/types/features";

// FIRST step of the processing workflow
export const Route = createFileRoute("/app/$feature/onboarding")({
  component: RouteComponent,
});

interface GenericOnboardingProps {
  description: string;
  actionText: string;
  steps: string[];
  multipleFiles: boolean;
}
function GenericOnboarding({
  description,
  actionText,
  steps,
  multipleFiles,
}: GenericOnboardingProps) {
  const { feature } = useParams({ from: "/app/$feature/onboarding" });
  const inputRef = useRef<HTMLInputElement>(null);
  const dispatch = useFileDispatch();
  const navigate = useNavigate();

  const handleSelectFile = () => {
    inputRef.current?.click();
  };

  const handleAddedFiles: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    const rawFiles = e.target.files;

    // Check if any file was added
    if (rawFiles) {
      const files = Array.from(rawFiles);

      dispatch(addFiles(files));
      navigate({
        to: "/app/$feature/preview",
        params: { feature },
      });
    }
  };

  return (
    <>
      {/* Onboarding description */}
      <Section spacing="xl">
        <Stack spacing="m">
          <Title weight="strong">¿Cómo funciona AymurAI?</Title>
          <Text>{description}</Text>
        </Stack>
        <OnboardingGrid>
          {steps.map((step, index) => (
            <OnboardingCard key={step} step={index + 1} text={step} />
          ))}
        </OnboardingGrid>
      </Section>

      {/* Input file */}
      <Footer>
        <HiddenInput
          type="file"
          accept=".docx, .pdf"
          ref={inputRef}
          onChange={handleAddedFiles}
          multiple={multipleFiles}
          tabIndex={-1}
        />
        <Text size="s">Formatos válidos: .docx, .pdf</Text>
        <Button onClick={handleSelectFile} size="l">
          {actionText}
        </Button>
      </Footer>
    </>
  );
}

function RouteComponent() {
  const { feature } = useParams({
    from: "/app/$feature/onboarding",
  });

  if (feature === Feature.Dataset)
    return (
      <GenericOnboarding
        description="Esta herramienta te permitirá subir las resoluciones del juzgado para que sean analizadas por una inteligencia artificial que extraerá la información relevante para el set de datos abiertos con perspectiva de género."
        actionText="Selecciona los archivos"
        steps={[
          "Selecciona los archivos",
          "La inteligencia artificial procesará los archivos",
          "Valida que la información identificada sea correcta",
          "Proceso terminado. Los archivos ya son parte del set de datos.",
        ]}
        multipleFiles={true}
      />
    );

  return (
    <GenericOnboarding
      description="Esta herramienta te permitirá subir las resoluciones del juzgado para que sean analizadas por una inteligencia artificial que anonimizará los datos sensibles de las personas involucradas y de los hechos del caso."
      actionText="Selecciona el archivo"
      steps={[
        "Selecciona el archivo",
        "La inteligencia artificial procesará el archivo",
        "Valida que la información a anonimizar sea correcta",
        "Proceso terminado. El documento esta listo para ser exportado.",
      ]}
      multipleFiles={false}
    />
  );
}
