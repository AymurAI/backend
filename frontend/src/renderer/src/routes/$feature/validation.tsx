import { Button, FileAnnotator, ValidateDataset } from "@/components";
import Stepper from "@/components/home/stepper";
import Footer from "@/components/layout/footer";
import Header from "@/components/layout/header";
import HomeButton from "@/components/layout/home-button";
import RequireFile from "@/features/RequireFile";
import { useFiles } from "@/hooks";
import { Grid, Stack } from "@/styled/jsx";
import { FeatureFlowEnum, featureNamespace, getFeatureRouteSlug, parseFeatureRouteSlug } from "@/types/features";
import {
  Navigate,
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

export const Route = createFileRoute("/$feature/validation")({
  component: RouteComponent,
});

function RouteComponent() {
  const { feature: featureSlug } = useParams({
    from: "/$feature/validation",
  });
  const feature = parseFeatureRouteSlug(featureSlug);

  const navigate = useNavigate();

  if (!feature) return <Navigate to="/home/features" />;

  const { t } = useTranslation(featureNamespace[feature]);

  const file = useFiles()[0]!;

  const handleContinue = () =>
    navigate({ to: "/$feature/finish", params: { feature: getFeatureRouteSlug(feature) } });

  if (feature === FeatureFlowEnum.Anonymizer)
    return (
      <RequireFile>
        <Stack width="screen" height="screen" gap="0">
          <Header
            title={t("title")}
            center={<Stepper currentStep={3} />}
            feature={feature}
            right={<HomeButton />}
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
        </Stack>
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
