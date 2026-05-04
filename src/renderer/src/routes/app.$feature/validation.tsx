import { Button, FileAnnotator, ValidateDataset } from "@/components";
import Stepper from "@/components/home/stepper";
import Footer from "@/components/layout/footer";
import Header from "@/components/layout/header";
import RequireFile from "@/features/RequireFile";
import { useFiles } from "@/hooks";
import { Grid, Stack } from "@/styled/jsx";
import { FeatureFlowEnum, featureNamespace } from "@/types/features";
import {
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

export const Route = createFileRoute("/app/$feature/validation")({
  component: RouteComponent,
});

function RouteComponent() {
  const { feature } = useParams({
    from: "/app/$feature/validation",
  });

  const navigate = useNavigate();
  const { t } = useTranslation(featureNamespace[feature]);

  const file = useFiles()[0]!;

  const handleContinue = () =>
    navigate({ to: "/app/$feature/finish", params: { feature } });

  if (feature === FeatureFlowEnum.Anonymizer)
    return (
      <RequireFile>
        <Header
          title={t("title")}
          center={<Stepper currentStep={3} />}
          feature={feature}
        />
        <Grid
          columns={1}
          gap="0"
          justifyContent="stretch"
          alignItems="stretch"
          style={{ overflow: "hidden" }}
        >
          <FileAnnotator {...{ file }} isAnnotable />
        </Grid>

        <Footer>
          <Button size="md" onClick={handleContinue}>
            Anonimizar documento
          </Button>
        </Footer>
      </RequireFile>
    );
  return (
    <RequireFile>
      <Stack gap="0" height="screen" overflow="hidden">
        <Header
          title={t("title")}
          center={<Stepper currentStep={3} />}
          feature={feature}
        />
        <ValidateDataset />
      </Stack>
    </RequireFile>
  );
}
