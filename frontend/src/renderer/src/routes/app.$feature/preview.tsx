import {
  Button,
  Card,
  FilePreview,
  Grid,
  HiddenInput,
  SectionTitle,
  Subtitle,
  Text,
} from "@/components";
import { useFileDispatch, useFiles } from "@/hooks";
import { Footer, Section } from "@/layout/main";
import {
  addFiles,
  filterUnselected,
  removeAllFiles,
} from "@/reducers/file/actions";
import { Feature } from "@/types/features";
import {
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { useRef } from "react";

export const Route = createFileRoute("/app/$feature/preview")({
  component: RouteComponent,
});

interface GenericPreviewProps {
  title: string;
  supportMultipleFiles: boolean;
}
function GenericPreview({ title, supportMultipleFiles }: GenericPreviewProps) {
  const { feature } = useParams({ from: "/app/$feature/preview" });
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const files = useFiles();
  const dispatch = useFileDispatch();

  const isAnyFileSelected = files.some((file) => file.selected);

  const handlePrevious = () => {
    dispatch(removeAllFiles());
    navigate({
      to: "/app/$feature/onboarding",
      params: { feature },
    });
  };

  const handleSelectFile = () => {
    inputRef.current?.click();
  };

  const handleAddedFiles: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    const rawFiles = e.target.files;

    // Check if any file was added
    if (rawFiles) {
      const fileArray = Array.from(rawFiles);

      dispatch(addFiles(fileArray));
    }
  };

  const handleConfirmFiles = () => {
    dispatch(filterUnselected());
    navigate({
      to: "/app/$feature/process",
      params: { feature },
    });
  };

  return (
    <>
      {/* MAIN SECTION */}
      <Section spacing="xl">
        <SectionTitle onClick={handlePrevious}>{title}</SectionTitle>
        <Card>
          {supportMultipleFiles && <Subtitle>Archivos seleccionados</Subtitle>}
          <Grid
            columns={supportMultipleFiles ? 5 : 1}
            spacing="xl"
            justify="center"
            css={{ width: "100%" }}
          >
            {files.map((file) => (
              <FilePreview key={file.data.name} file={file} />
            ))}
          </Grid>
        </Card>
      </Section>

      {/* FOOTER */}
      <Footer>
        <HiddenInput
          type="file"
          accept=".docx"
          ref={inputRef}
          onChange={handleAddedFiles}
          multiple
          tabIndex={-1}
        />
        {supportMultipleFiles && (
          <>
            <Text size="s">Formatos válidos: .docx, .pdf</Text>
            <Button onClick={handleSelectFile} size="l" variant="secondary">
              Cargar más documentos
            </Button>
          </>
        )}
        <Button
          onClick={handleConfirmFiles}
          disabled={
            !isAnyFileSelected || files.some((f) => !f.paragraphs?.length)
          }
          size="l"
        >
          Continuar
        </Button>
      </Footer>
    </>
  );
}

function RouteComponent() {
  const { feature } = useParams({
    from: "/app/$feature/preview",
  });

  if (feature === Feature.Dataset)
    return (
      <GenericPreview
        supportMultipleFiles={true}
        title="1. Previsualización de archivos"
      />
    );

  return (
    <GenericPreview
      supportMultipleFiles={false}
      title="1. Previsualización del archivo"
    />
  );
}
