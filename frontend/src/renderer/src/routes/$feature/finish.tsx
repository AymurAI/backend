import FinishAnonymizer from "@/components/finish/finish-anonymizer";
import FinishDataset from "@/components/finish/finish-dataset";
import Stepper from "@/components/home/stepper";
import Header from "@/components/layout/header";
import HomeButton from "@/components/layout/home-button";
import RequireFile from "@/features/RequireFile";
import { useFileDispatch } from "@/hooks";
import { Stack } from "@/styled/jsx";
import { removeAllFiles } from "@/reducers/file/actions";
import { FeatureFlowEnum, featureNamespace, getFeatureRouteSlug, parseFeatureRouteSlug } from "@/types/features";
import {
  Navigate,
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

export const Route = createFileRoute("/$feature/finish")({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const { feature: featureSlug } = useParams({ from: "/$feature/finish" });
  const feature = parseFeatureRouteSlug(featureSlug);

  if (!feature) return <Navigate to="/home/features" />;

  const { t } = useTranslation(featureNamespace[feature]);
  const dispatch = useFileDispatch();

  const handleRestart = () => {
    dispatch(removeAllFiles());
    navigate({ to: "/$feature/onboarding", params: { feature: getFeatureRouteSlug(feature) } });
  };

  return (
    <RequireFile>
      <Stack width="screen" minHeight="screen" gap="0">
        <Header
        title={t("title")}
        center={
          feature === FeatureFlowEnum.Dataset ? (
            <Stepper currentStep={4} />
          ) : undefined
        }
        right={<HomeButton />}
      />

        {feature === FeatureFlowEnum.Dataset ? (
        <FinishDataset onRestart={handleRestart} />
        ) : (
        <FinishAnonymizer onRestart={handleRestart} />
        )}
      </Stack>
    </RequireFile>
  );
}
