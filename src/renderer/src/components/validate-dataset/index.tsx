import { useState } from "react";

import {
  Button,
  FileAnnotator,
  FileStepper,
  Grid,
  SectionTitle,
} from "@/components";
import { useFileDispatch, useFiles } from "@/hooks";
import { Footer, Section } from "@/layout/main";
import { validate } from "@/reducers/file/actions";
import { isFileValidated, isValidationCompleted } from "@/utils/file";
import { useNavigate, useParams } from "@tanstack/react-router";
import FormGroup from "./form-group";
import { moveNext, movePrevious } from "./utils";

export function ValidateDataset() {
  // HOOKS
  const { feature } = useParams({ from: "/app/$feature/validation" });
  const files = useFiles();
  const [checked, setChecked] = useState(false);
  const [selected, setSelected] = useState(0);
  const dispatch = useFileDispatch();
  const navigate = useNavigate();

  // FIELDS
  const hasStepper = files.length > 1;

  const selectedFile = files[selected];
  // Check if the validation was completed on all the files
  const canContinue = isValidationCompleted(files);
  const canValidate = isFileValidated(selectedFile);

  // HANDLERS
  const moveIndex = (newIndex: number | undefined) => {
    if (newIndex !== undefined) setSelected(newIndex);
  };
  const nextFile = () => moveIndex(moveNext(selected, files));
  const previousFile = () => moveIndex(movePrevious(selected, files));

  const handleContinue = () => {
    navigate({
      to: "/app/$feature/finish",
      params: { feature },
    });
  };

  const handleValidate = async () => {
    // Set validated = true so the file is no longer accesible through the FileStepper component
    dispatch(validate(selectedFile.data.name));

    if (canContinue || !hasStepper) {
      handleContinue();
    } else {
      nextFile();
    }
  };

  const handleCheck = (checked: boolean) => {
    setChecked(checked);
  };

  return (
    <>
      <Grid
        columns={2}
        spacing="none"
        justify="stretch"
        align="stretch"
        css={{ overflow: "hidden" }}
      >
        <FileAnnotator
          key={selectedFile.data.name}
          file={selectedFile}
          isAnnotable
        />
        <Section css={{ px: 100, overflowY: "scroll" }} spacing="xxl">
          <SectionTitle>3. Validación de datos</SectionTitle>
          <FormGroup
            key={selectedFile.data.name}
            file={selectedFile}
            onCheck={handleCheck}
          />
        </Section>
      </Grid>
      <Footer
        css={{
          justifyContent: hasStepper ? "space-between" : "flex-end",
          gap: 150,
        }}
      >
        {hasStepper && (
          <FileStepper {...{ selected, nextFile, previousFile }} />
        )}

        {canContinue ? (
          <Button size="l" onClick={handleContinue}>
            Continuar
          </Button>
        ) : (
          <Button
            size="l"
            onClick={handleValidate}
            disabled={!checked && !canValidate}
          >
            Validar documento
          </Button>
        )}
      </Footer>
    </>
  );
}
