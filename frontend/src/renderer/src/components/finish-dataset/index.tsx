import { useEffect, useState } from "react";

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
import filesystem from "@/services/filesystem";
import type { DocFile } from "@/types/file";
import { submitValidations } from "@/utils/file";
import { useNavigate, useParams } from "@tanstack/react-router";
import * as S from "./FinishDataset.styles";

export function FinishDataset() {
  const params = useParams({ from: "/app/$feature/finish" });
  const files = useFiles();
  const dispatch = useFileDispatch();
  const navigate = useNavigate();
  const [errorNames, setErrorNames] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const handleRestart = () => {
    dispatch(removeAllFiles());
    navigate({ to: "/app/$feature/onboarding", params });
  };

  const checkForErrors = (fileName: string) =>
    !!errorNames.find((name) => name === fileName);

  const submit = async (file: DocFile) => {
    try {
      // POST the validated data to the dataset
      await submitValidations({
        isOnline: false,
        validations: file.validationObject,
      });
    } catch {
      setErrorNames((names) => [...names, file.data.name]);
    }

    // Export the feedback JSON
    await filesystem.feedback.export(files);
  };

  // At first render, submit all the data
  useEffect(() => {
    const submitAll = async () => {
      for (const file of files) {
        await submit(file);
      }
    };

    submitAll().then(() => setIsLoading(false));

    // We strictly need to run this effect once
  }, []);

  return (
    <>
      <Section>
        <SectionTitle>4. Finalización</SectionTitle>
        <Text css={{ maxWidth: "60%" }}>
          Los datos encontrados por AymurAI y posteriormente validados ya son
          parte del set de datos abiertos con perspectiva de género.
        </Text>

        <Card>
          <Subtitle>Archivos procesados</Subtitle>
          <Grid
            columns={4}
            spacing="xl"
            justify="center"
            css={{ width: "100%" }}
          >
            {files.map(({ data }) => (
              <FileCheck
                key={data.name}
                fileName={data.name}
                hasError={checkForErrors(data.name)}
                {...{ isLoading }}
              />
            ))}
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
          Cargar más documentos
        </Button>
        <Button size="l" onClick={filesystem.excel.open}>
          Ver set de datos
        </Button>
      </Footer>
    </>
  );
}
