import { useState } from "react";

import { Button, FileAnnotator, FileStepper, Grid } from "@/components";
import Footer from "@/components/layout/footer";
import { useFileDispatch, useFiles } from "@/hooks";
import { SectionTitle } from "@/layout/section-title";
import { validate } from "@/reducers/file/actions";
import { css } from "@/styled/css";
import { HStack, Stack } from "@/styled/jsx";
import { isFileValidated, isValidationCompleted } from "@/utils/file";
import { getFeatureRouteSlug, parseFeatureRouteSlug } from "@/types/features";
import { Navigate, useNavigate, useParams } from "@tanstack/react-router";
import FormGroup from "./form-group";
import { moveNext, movePrevious } from "./utils";

export function ValidateDataset() {
  // HOOKS
  const { feature: featureSlug } = useParams({ from: "/$feature/validation" });
  const feature = parseFeatureRouteSlug(featureSlug);

  if (!feature) return <Navigate to="/home/features" />;
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
      to: "/$feature/finish",
      params: { feature: getFeatureRouteSlug(feature) },
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
    <Stack gap="0" flex="1" minHeight="0">
      <Grid
        columns={2}
        spacing="none"
        justify="stretch"
        align="stretch"
        css={{ overflow: "hidden", flex: 1, minHeight: 0 }}
      >
        <FileAnnotator
          key={selectedFile.data.name}
          file={selectedFile}
          isAnnotable={false}
        />
        <Stack
          px="[100px]"
          pt="16"
          pb="16"
          overflowY="scroll"
          gap="16"
          bg="bg.primary"
          minHeight="0"
        >
          <SectionTitle className={css({ whiteSpace: "nowrap" })}>
            3. Validación de datos
          </SectionTitle>
          <FormGroup
            key={selectedFile.data.name}
            file={selectedFile}
            onCheck={handleCheck}
          />
        </Stack>
      </Grid>
      <Footer>
        <HStack
          alignItems="center"
          width="full"
          justify={hasStepper ? "space-between" : "flex-end"}
          gap="36"
        >
          {hasStepper && (
            <FileStepper {...{ selected, nextFile, previousFile }} />
          )}

          {canContinue ? (
            <Button size="md" onClick={handleContinue}>
              Continuar
            </Button>
          ) : (
            <Button
              size="md"
              onClick={handleValidate}
              disabled={!checked && !canValidate}
            >
              Validar documento
            </Button>
          )}
        </HStack>
      </Footer>
    </Stack>
  );
}
