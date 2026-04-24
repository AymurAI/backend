import {
  Button,
  Card,
  FileCheck,
  Grid,
  SectionTitle,
  Subtitle,
  Text,
} from "@/components";
import { useFileDispatch, useFiles } from "@/hooks";
import { Footer, Section } from "@/layout/main";
import { removeAllFiles } from "@/reducers/file/actions";
import { aymuraiService } from "@/services/aymurai";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "@tanstack/react-router";
import * as S from "./FinishAnonymizer.styles";

const changeExtension = (name: string) => {
  const parts = name.split(".");
  parts.pop();
  return `${[...parts].join(".")}_anonimizado.odt`;
};

export function FinishAnonymizer() {
  const params = useParams({ from: "/app/$feature/finish" });
  // We are sure that there is only one file, because we came from
  // anonimization workflow
  const file = useFiles()[0];
  const dispatch = useFileDispatch();
  const navigate = useNavigate();

  const {
    data: fileURI,
    isLoading,
    isError,
  } = useQuery(aymuraiService.anonymize(file));

  const downloadDocument = async () => {
    if (!fileURI) {
      console.error("Tried to download a file that is not ready.");
      return;
    }
    const link = document.createElement("a");
    link.href = fileURI;
    link.download = changeExtension(file.data.name);

    link.click();

    document.removeChild(link);
  };

  const handleRestart = () => {
    dispatch(removeAllFiles());
    navigate({ to: "/app/$feature/onboarding", params });
  };

  return (
    <>
      <Section>
        <SectionTitle>4. Finalización</SectionTitle>
        <Text css={{ maxWidth: "60%" }}>
          Los datos encontrados por AymurAI y posteriormente validados ya han
          sido anonimizados correctamente.
        </Text>
        <Card>
          <Subtitle>Archivo procesado</Subtitle>
          <Grid
            columns={4}
            spacing="xl"
            justify="center"
            css={{ width: "100%" }}
          >
            <FileCheck
              fileName={file.data.name}
              hasError={isError}
              isLoading={isLoading}
            />
          </Grid>
        </Card>
      </Section>
      <Footer>
        <S.Anchor
          href="https://www.datagenero.org/"
          target="_blank"
          rel="noreferrer"
        >
          <img src="brand/data-genero.png" alt="DataGenero" width={150} />
        </S.Anchor>
        <Button variant="secondary" onClick={handleRestart} size="l">
          Cargar un nuevo documento
        </Button>
        <Button onClick={downloadDocument} size="l" disabled={isError}>
          Descargar documento
        </Button>
      </Footer>
    </>
  );
}
